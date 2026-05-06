# ModelServe — Simple Command Guide

Quick commands to start and test the system.

---

## Quick Start (One-Time Setup)

```bash
cd /home/poridhian/code/MLOps-S2-Exam1-modelserve-capstone

# Install dependencies (one time)
python3 -m venv mlops_venv
source mlops_venv/bin/activate
pip install -r requirements.txt
pip install -r infrastructure/requirements.txt
```

---

## Start Everything (Local)

```bash
cd /home/poridhian/code/MLOps-S2-Exam1-modelserve-capstone
docker compose up -d
```

Wait 30 seconds for services to start, then:

```bash
# Materialize features to Redis
docker compose exec -T fastapi /bin/bash -c "cd /app/feast_repo && feast materialize-incremental \$(date -u +%Y-%m-%dT%H:%M:%S)"
```

---

## Test It

```bash
# Health check
curl http://localhost:8000/health

# Make prediction (use entity_id from training/sample_request.json)
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"entity_id": 340187018810220}'

# View metrics in Prometheus format
curl http://localhost:8000/metrics
```

---

## Web UIs

| Service | URL | Login |
|---------|-----|-------|
| FastAPI | http://localhost:8000 | - |
| MLflow | http://localhost:5000 | - |
| Prometheus | http://localhost:9090 | - |
| Grafana | http://localhost:3000 | admin/admin |

---

## Train New Model

```bash
cd /home/poridhian/code/MLOps-S2-Exam1-modelserve-capstone
source mlops_venv/bin/activate
python training/train.py
```

---

## AWS Infrastructure (Pulumi)

```bash
cd infrastructure

# Install Pulumi (one time)
curl -fsSL https://get.pulumi.com | sh
export PATH="$HOME/.pulumi/bin:$PATH"

# Create AWS resources
pulumi up
```

---

## Stop

```bash
docker compose down
```

---

## Troubleshooting

```bash
# Check what's running
docker compose ps

# View logs
docker compose logs -f fastapi
docker compose logs -f mlflow

# Restart a service
docker compose restart fastapi

# Re-materialize features
docker compose exec -T fastapi /bin/bash -c "cd /app/feast_repo && feast materialize-incremental \$(date -u +%Y-%m-%dT%H:%M:%S)"
```

---

## System Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ HTTP
       ▼
┌─────────────┐     ┌─────────────┐
│  FastAPI    │────▶│   Redis     │
│  :8000      │     │  (Feast)    │
└──────┬──────┘     └─────────────┘
       │
       │ Load Model
       ▼
┌─────────────┐     ┌─────────────┐
│   MLflow    │────▶│ PostgreSQL  │
│   :5000     │     │   :5432     │
└─────────────┘     └─────────────┘
       │
       │ Scrape Metrics
       ▼              ▼
┌─────────────┐   ┌─────────────┐
│ Prometheus  │   │  Grafana    │
│   :9090     │   │   :3000     │
└─────────────┘   └─────────────┘
```