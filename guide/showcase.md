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

## Quick Reference

| Service | Port | URL |
|---------|------|-----|
| FastAPI | 8000 | http://localhost:8000 |
| MLflow | 5000 | http://localhost:5000 |
| Prometheus | 9090 | http://localhost:9090 |
| Grafana | 3000 | http://localhost:3000 |
| PostgreSQL | 5432 | localhost:5432 |
| Redis | 6379 | localhost:6379 |

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