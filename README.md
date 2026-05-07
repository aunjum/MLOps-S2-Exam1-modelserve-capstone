# ModelServe

> MLOps with Cloud Season 2 — Capstone Exam

A production-ready fraud detection inference service with MLflow model registry, Feast feature store, Prometheus monitoring, and Grafana dashboards.

## Prerequisites

- Docker and Docker Compose
- Python 3.12+
- AWS account (for Pulumi infrastructure)
- Redis, PostgreSQL (provided via Docker Compose)

## Quick Start (Local Development)

```bash
# 1. Start all services
docker-compose up -d

# 2. Wait for services to be healthy (check with:)
docker ps

# 3. Train the model
source mlops_venv/bin/activate
python training/train.py

# 4. Materialize features to Redis (from host or container)
# From host:
python -c "
from feast import FeatureStore
from datetime import datetime, timezone
fs = FeatureStore(repo_path='./feast_repo')
fs.materialize(start_date=datetime(2024,1,1,tzinfo=timezone.utc), end_date=datetime.now(timezone.utc))
"
# Or from container:
docker exec modelserve-fastapi python -c "
from feast import FeatureStore
from datetime import datetime, timezone
fs = FeatureStore(repo_path='/app/feast_repo')
fs.materialize(start_date=datetime(2024,1,1,tzinfo=timezone.utc), end_date=datetime.now(timezone.utc))
"

# 5. Test the API
curl http://localhost:8000/health
curl -X POST http://localhost:8000/predict -H "Content-Type: application/json" -d '{"entity_id": 340187018810220}'
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| FastAPI | 8000 | Inference API |
| MLflow | 5000 | Model registry & tracking |
| Prometheus | 9090 | Metrics collection |
| Grafana | 3001 | Dashboards |
| PostgreSQL | 5432 | MLflow backend store |
| Redis | 6379 | Feast online store |

## REST Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check with model version |
| POST | `/predict` | Make fraud prediction |
| GET | `/predict/{entity_id}?explain=true` | Prediction with feature values |
| GET | `/metrics` | Prometheus metrics |

## Environment Variables

See `.env.example` for all required variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `POSTGRES_USER` | PostgreSQL username | mlflow |
| `POSTGRES_PASSWORD` | PostgreSQL password | mlflow |
| `MLFLOW_TRACKING_URI` | MLflow server URI | http://localhost:5000 |
| `MODEL_NAME` | Model name in registry | FraudDetector |
| `MODEL_STAGE` | Model stage to load | Production |
| `REDIS_HOST` | Redis host | redis |
| `REDIS_PORT` | Redis port | 6379 |

## GitHub Secrets

| Secret | Purpose |
|--------|---------|
| `AWS_ACCESS_KEY_ID` | AWS credentials for S3 |
| `AWS_SECRET_ACCESS_KEY` | AWS credentials for S3 |
| `AWS_REGION` | AWS region | ap-southeast-1 |

## Engineering Documentation

- **[docs/README.md](docs/README.md)** — documentation index
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — system overview, Mermaid architecture diagrams, five ADRs, CI/CD, runbook, known limitations
- **[docs/diagrams/](docs/diagrams/)** — how to export diagrams from the Mermaid in `ARCHITECTURE.md`
- **[guide/issues.md](guide/issues.md)** — known issues and troubleshooting

## Dataset

[Credit Card Transactions Fraud Detection](https://www.kaggle.com/datasets/kartik2112/fraud-detection) — Simulated credit card transactions generated using Sparkov. Use `fraudTrain.csv` (~1.3M rows, 22 features). Entity key: `cc_num`.

---

*MLOps with Cloud Season 2 — Capstone: ModelServe | Poridhi.io*