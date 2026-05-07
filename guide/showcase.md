# ModelServe — How It Works

A fraud detection inference system. This document explains **why** each component exists, **what** it does, and **how** the data flows.

---

## The Problem

Credit card companies need to predict if a transaction is fraud in **real-time**. They need:
- Fast feature lookups (what's the customer's recent behavior?)
- A trained model (RandomForest)
- Monitoring (is the API working? how fast?)
- CI/CD (automatic deployment to AWS)

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT REQUEST                              │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      FASTAPI (:8000)                                │
│   /health, /predict, /metrics                                       │
└─────────────────────────────────────────────────────────────────────┘
         │                           │                       │
         ▼                           ▼                       ▼
┌──────────────────┐      ┌──────────────────┐      ┌──────────────┐
│  FEATURE STORE   │      │    MLFLOW        │      │  PROMETHEUS  │
│  (Feast + Redis) │      │  (Model Registry)│      │  (:9090)     │
│  :6379           │      │   :5000          │      │              │
└──────────────────┘      └──────────────────┘      └──────────────┘
                                                            │
                                                            ▼
                                                    ┌──────────────┐
                                                    │   GRAFANA    │
                                                    │   (:3000)    │
                                                    └──────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                      POSTGRES (:5432)                               │
│              MLflow Backend Store (metadata)                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Component-by-Component

### 1. Training → MLflow

**File:** `training/train.py`

```
┌─────────────────┐      ┌──────────────┐      ┌─────────────────┐
│  fraudTrain.csv │ ───► │ RandomForest │ ───► │ MLflow Registry │
│  (Kaggle data)  │      │   Trainer    │      │ (Production)    │
└─────────────────┘      └──────────────┘      └─────────────────┘
                                                        │
                                                        ▼
                                              ┌─────────────────┐
                                              │features.parquet│
                                              │  (for Feast)   │
                                              └─────────────────┘
```

**What happens:**
1. Load fraud data (1.3M transactions)
2. Engineer features: `amt`, `category_enc`, `trans_hour`, `trans_dow`, `city_pop`, `merch_lat`, `merch_long`
3. Train RandomForest with `class_weight=balanced` (fraud is rare)
4. Log metrics to MLflow: F1, precision, recall, ROC-AUC
5. Register model as "FraudDetector"
6. Auto-transition to "Production" stage
7. Export latest features to `features.parquet`

**Why:** MLflow tracks experiments, versions models, and serves them to production.

---

### 2. Feature Store → Feast + Redis

**Files:** `feast_repo/feature_store.yaml`, `feast_repo/feature_definitions.py`

```
┌─────────────────┐      ┌──────────────┐      ┌─────────────────┐
│ features.parquet│ ───► │    Feast     │ ───► │   Redis (online)│
│  (offline)      │      │ materialize  │      │   :6379         │
└─────────────────┘      └──────────────┘      └─────────────────┘
```

**What happens:**
1. Feast loads feature definitions (7 features per `cc_num`)
2. `feast materialize` copies data from parquet → Redis
3. At inference time: Redis lookup is **sub-millisecond**

**Why Redis?** Feature lookups must be fast. Redis stores hot features in memory.

---

### 3. Inference → FastAPI

**Files:** `app/main.py`, `app/feature_client.py`, `app/model_loader.py`

```
CLIENT ──POST /predict──► FASTAPI
                              │
                              ├──► Feast Client ──► Redis (get features)
                              │
                              ├──► Model Loader ──► MLflow (load model)
                              │
                              ▼
                         PREDICTION
                              │
                              ├──► Metrics ──► Prometheus
                              │
                              ▼
                         JSON response
```

**What happens:**
1. **Startup:** FastAPI loads model from MLflow (`models:/FraudDetector/Production`)
2. **Request:** `POST /predict` with `entity_id` (credit card number)
3. **Features:** `FeatureClient.get_features(entity_id)` → Redis lookup
4. **Predict:** `ModelLoader.predict(features)` → RandomForest inference
5. **Response:** `{"prediction": 0/1, "probability": 0.0-1.0, "model_version": "1"}`
6. **Metrics:** Record latency, hits/misses, errors

**Code flow (simplified):**
```python
# app/main.py - predict endpoint
features = feature_client.get_features(entity_id)   # Redis via Feast
result = model_loader.predict(features)              # MLflow model
metrics.record_prediction(duration)                  # Prometheus
return result
```

---

### 4. Monitoring → Prometheus + Grafana

**Files:** `app/metrics.py`, `monitoring/prometheus/prometheus.yml`, `monitoring/grafana/`

```
FASTAPI /metrics ───────────────► PROMETHEUS ───────────────► GRAFANA
(prediction_requests_total,      (scrape every 10s)          (dashboards)
 prediction_duration_seconds,
 feast_online_store_hits_total,
 feast_online_store_misses_total)
```

**Metrics collected:**
| Metric | Type | Purpose |
|--------|------|---------|
| `prediction_requests_total` | Counter | How many requests? |
| `prediction_duration_seconds` | Histogram | How fast? |
| `prediction_errors_total` | Counter | Any failures? |
| `feast_online_store_hits_total` | Counter | Cache hit rate |
| `feast_online_store_misses_total` | Counter | Missing features? |
| `model_version_info` | Gauge | Which model version? |

**Alerts (prometheus/alerts.yml):**
- `ServiceDown` — API unreachable for 1 minute
- `HighPredictionLatency` — p95 > 1 second for 5 minutes
- `HighErrorRate` — errors > 5% for 2 minutes

---

### 5. Deployment → CI/CD (GitHub Actions)

**File:** `.github/workflows/deploy.yml`

```
GITHUB PUSH TO MAIN
        │
        ├──► TEST: pytest app/tests/
        │
        ├──► BUILD: docker build → ECR
        │
        └──► DEPLOY: scp to EC2 → docker-compose up

AWS EC2 (t3.small)
┌─────────────────────────────────────┐
│ Docker Compose Stack                │
│ - fastapi, mlflow, postgres, redis  │
│ - prometheus, grafana               │
└─────────────────────────────────────┘
```

**Infrastructure (Pulumi):**
- Creates VPC, EC2, S3 bucket, ECR repository
- File: `infrastructure/__main__.py`

---

## How to Demo the System

### 1. Start everything
```bash
docker compose up -d
```

Wait 30 seconds for services to be healthy.

### 2. Test the API
```bash
# Health check
curl http://localhost:8000/health
# {"status":"healthy","model_version":"1"}

# Make prediction
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"entity_id": 340187018810220}'
# {"prediction":0,"probability":0.0,"model_version":"1",...}
```

### 3. View MLflow
```
http://localhost:5000
```
- See "FraudDetector" model
- Check metrics (F1, precision, recall)
- Model in "Production" stage

### 4. View Prometheus
```
http://localhost:9090
```
- Query: `prediction_requests_total`
- Query: `prediction_duration_seconds`
- Query: `up` (service status)

### 5. View Grafana
```
http://localhost:3000 (admin/admin)
```
- Dashboards → ModelServe
- See request rate, latency, Feast hits/misses

---

---

## Infrastructure Checking (Pulumi)

**File:** `infrastructure/__main__.py`

```bash
# Check infrastructure status
pulumi stack
# Output: aws (ap-southeast-1)

# View outputs
pulumi stack output
# instance_ip: 1.2.3.4
# ecr_repository_url: 123456789012.dkr.ecr.ap-southeast-1.amazonaws.com/fastapi-app
# s3_bucket_name: modelserve-mlflow-artifacts
# security_group_id: sg-0123456789abcdef0
```

**What Pulumi creates:**
| Resource | Description |
|----------|-------------|
| VPC (10.0.0.0/16) | Isolated network |
| Subnet (10.0.1.0/24) | Public subnet |
| EC2 (t3.small) | Compute with Docker |
| EIP | Static IP |
| S3 Bucket | MLflow artifacts storage |
| ECR | Container registry |
| Security Group | Ports 22, 8000, 3000, 5000, 9090 |

**Why Pulumi?**
- **IaC**: Infrastructure as Code, version controlled
- **Reproducible**: Destroy and recreate in minutes
- **Multi-cloud**: AWS, Azure, GCP support

---

## CI/CD Pipeline (GitHub Actions)

**File:** `.github/workflows/deploy.yml`

```bash
# Trigger: Push to main branch
# Pipeline flow:
# 1. TEST: pytest app/tests/
# 2. BUILD: docker build → ECR
# 3. DEPLOY: SSH to EC2 → docker-compose up
```

**Workflow Jobs:**
| Job | Description | Secrets Required |
|-----|-------------|------------------|
| test | Run pytest | None |
| build-and-push | Build Docker → ECR | AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, ECR_REGISTRY |
| deploy | SSH + deploy | EC2_HOST, EC2_USER, EC2_SSH_KEY |

**Secrets to Configure:**
```bash
# GitHub → Settings → Secrets and variables → Actions
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
ECR_REGISTRY=123456789012.dkr.ecr.ap-southeast-1.amazonaws.com
EC2_HOST=1.2.3.4
EC2_USER=ubuntu
EC2_SSH_KEY=-----BEGIN RSA PRIVATE KEY-----\n...
```

**Deployment Verification:**
```bash
# After deploy, check health
curl http://<EC2_HOST>:8000/health
# {"status":"healthy","model_version":"1"}
```

---

## Feast Feature Store

**Files:** `feast_repo/feature_store.yaml`, `feast_repo/feature_definitions.py`

**Architecture:**
```
features.parquet (offline) ──► feast materialize ──► Redis (online)
                                         │
                                   Registry (metadata)
```

**Feature Definitions:**
```python
# feast_repo/feature_definitions.py
feast.Feature(
    name="amt",
    dtype=feast.types.Float32,
    description="Transaction amount",
)
# + 6 more: category_enc, trans_hour, trans_dow, city_pop, merch_lat, merch_long
```

**Materialization:**
```bash
# Materialize features from parquet → Redis
docker exec modelserve-fastapi python -c "
from feast import FeatureStore
from datetime import datetime, timezone
fs = FeatureStore(repo_path='/app/feast_repo')
fs.materialize(
    start_date=datetime(2024,1,1,tzinfo=timezone.utc),
    end_date=datetime.now(timezone.utc)
)"
```

**Feature Lookup at Inference:**
```python
# app/feature_client.py
features = feature_client.get_features(entity_id)
# Returns: {"amt": 50.0, "category_enc": 3, "trans_hour": 14, ...}
```

**Why Feast?**
- **Online store**: Sub-millisecond Redis lookup
- **Offline store**: Batch processing from parquet/S3
- **Feature registry**: Versioned feature definitions
- **Consistency**: Same features for training and serving

---

## Feature Engineering

**File:** `training/train.py`

**7 Features for Fraud Detection:**

| Feature | Description | Engineering |
|---------|-------------|--------------|
| `amt` | Transaction amount | Raw |
| `category_enc` | Merchant category | Label encoding |
| `trans_hour` | Hour of transaction | `dt.hour` |
| `trans_dow` | Day of week | `dt.weekday()` |
| `city_pop` | City population | Log transform |
| `merch_lat` | Merchant latitude | Geocoding |
| `merch_long` | Merchant longitude | Geocoding |

**Training Process:**
```python
# 1. Load 1.3M transactions from CSV
# 2. Feature engineering (above)
# 3. Train RandomForest
clf = RandomForestClassifier(
    n_estimators=100,
    max_depth=10,
    class_weight='balanced',  # Handle imbalanced fraud
    random_state=42
)
# 4. Log to MLflow
mlflow.log_metric("f1_score", 0.85)
mlflow.log_metric("precision", 0.90)
mlflow.log_metric("recall", 0.80)
# 5. Register model
mlflow.register_model("models:/FraudDetector/Production")
# 6. Export features.parquet for Feast
df.to_parquet("features.parquet")
```

**Feature Export for Feast:**
```python
# Export entity + features for materialization
features_df = df[['cc_num', 'amt', 'category_enc', 'trans_hour',
                   'trans_dow', 'city_pop', 'merch_lat', 'merch_long']]
features_df.to_parquet("features.parquet")
```

---

## Quick Reference

| Service | Port | URL |
|---------|------|-----|
| FastAPI | 8000 | http://localhost:8000 |
| MLflow | 5000 | http://localhost:5000 |
| Prometheus | 9090 | http://localhost:9090 |
| Grafana | 3001 | http://localhost:3001 (admin/admin) |
| PostgreSQL | 5432 | localhost:5432 |
| Redis | 6379 | localhost:6379 |

**Infrastructure Check:**
```bash
# Pulumi
pulumi stack output

# Docker containers
docker ps

# EC2 SSH
ssh -i key.pem ubuntu@<instance_ip>
```

**CI/CD Check:**
```bash
# GitHub Actions → repo → Actions
# Verify: test → build-and-push → deploy
```

---

## Data Flow Summary

```
Training:       CSV → feature engineering → RandomForest → MLflow Registry
                                              ↓
                                     features.parquet (for Feast)

Serving:        Request → Feast/Redis → features → MLflow model → prediction
                              ↓
                         Prometheus metrics

Monitoring:     /metrics → Prometheus scrape → Grafana dashboards + alerts

Deployment:     GitHub push → test → build ECR → deploy EC2
```