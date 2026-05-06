# ModelServe — Quick Demo Guide

Simple commands to test the system and show it working.

---

## System Status (Quick Check)

```bash
# All running services
docker compose ps
```

Expected: All services show "Up" (fastapi, mlflow, redis, postgres, prometheus, grafana)

---

## Test Endpoints (The Demo)

### 1. Health Check
```bash
curl http://localhost:8000/health
```
**Expected:**
```json
{"status":"healthy","model_version":"1"}
```

### 2. Make a Prediction
```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"entity_id": 340187018810220}'
```
**Expected:**
```json
{"prediction":0,"probability":0.0,"model_version":"1","timestamp":"2026-05-06T...Z","features":null}
```

### 3. Get Prediction with Features
```bash
curl "http://localhost:8000/predict/340187018810220?explain=true"
```
**Expected:** Same as above but with `"features":{...}` included.

### 4. Prometheus Metrics
```bash
curl http://localhost:8000/metrics | grep prediction
```
**Expected:** Shows `prediction_requests_total`, `prediction_duration_seconds`, etc.

### 5. Prometheus Web UI
```
http://localhost:9090
```
- Go to "Graph" tab
- Query: `prediction_requests_total`
- Query: `up` — shows all service status

### 6. Grafana Web UI
```
http://localhost:3000
```
- Login: `admin` / `admin`
- Dashboards → ModelServe (if provisioned)
- Or manually add Prometheus datasource: `http://prometheus:9090`

### 7. MLflow Web UI
```
http://localhost:5000
```
- View registered model "FraudDetector"
- Check metrics (f1, precision, recall, roc_auc)

---

## Q&A for Demo

### Q: What does this system do?
A: It's a fraud detection API. You send a credit card number, it predicts if the transaction is fraud.

### Q: How does it work?
1. Features are loaded from Redis (Feast feature store)
2. Model is loaded from MLflow Registry (Production stage)
3. Prediction is made and returned with metrics

### Q: What technologies are used?
- **FastAPI**: REST API service
- **MLflow**: Model registry and experiment tracking
- **Feast**: Feature store (Redis for online, parquet for offline)
- **Prometheus**: Metrics collection
- **Grafana**: Dashboards
- **PostgreSQL**: MLflow backend storage

### Q: How do you deploy to AWS?
```bash
cd infrastructure
pulumi up  # Creates VPC, EC2, S3, ECR
# Then deploy using docker-compose on EC2
```

### Q: What happens when you call /predict?
1. Request hits FastAPI
2. Feature client fetches features from Redis (Feast)
3. Model loader gets model from MLflow
4. Prediction made, metrics recorded
5. Response returned with probability

### Q: How do you monitor the system?
- Prometheus scrapes `/metrics` from FastAPI every 15s
- Grafana visualizes the metrics
- Alert rules defined for: service down, high latency, high error rate

---

## One-Command Start

```bash
# Start everything
cd /home/poridhian/code/MLOps-S2-Exam1-modelserve-capstone
docker compose up -d
docker compose exec -T fastapi /bin/bash -c "cd /app/feast_repo && feast materialize-incremental \$(date -u +%Y-%m-%dT%H:%M:%S)"

# Test
curl http://localhost:8000/health
curl -X POST http://localhost:8000/predict -H "Content-Type: application/json" -d '{"entity_id": 340187018810220}'
```

---

## URLs Summary

| Service | URL |
|---------|-----|
| FastAPI | http://localhost:8000 |
| MLflow | http://localhost:5000 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 (admin/admin) |
| PostgreSQL | localhost:5432 (mlflow/mlflow) |
| Redis | localhost:6379 |

---

## Troubleshooting

```bash
# Check logs
docker compose logs -f fastapi
docker compose logs -f mlflow

# Restart a service
docker compose restart fastapi

# Rebuild after code changes
docker compose build fastapi
docker compose up -d

# Re-materialize features
docker compose exec -T fastapi /bin/bash -c "cd /app/feast_repo && feast materialize-incremental \$(date -u +%Y-%m-%dT%H:%M:%S)"
```