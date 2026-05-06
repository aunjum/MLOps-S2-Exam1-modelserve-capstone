# Architecture

## Overview

**ModelServe** is a fraud detection inference API. Client sends credit card number → FastAPI fetches features from Redis (Feast) → runs model from MLflow → returns prediction.

## Components

| Component | Technology | Purpose |
|-----------|------------|---------|
| API | FastAPI | Serves predictions at `/predict` |
| Model Registry | MLflow | Stores trained models, tracks experiments |
| Feature Store | Feast + Redis | Fast feature lookups at inference time |
| Monitoring | Prometheus + Grafana | Metrics, dashboards, alerts |
| Database | PostgreSQL | MLflow metadata storage |
| CI/CD | GitHub Actions | Test → Build → Deploy to AWS |

## Architecture Diagrams

### Local Development (Docker Compose)

```mermaid
flowchart TB
  subgraph dc["Docker Compose network: modelserve"]
    FEAST[("Feast repo\nfeast_repo")]
    PG[(PostgreSQL :5432)]
    RD[(Redis :6379)]
    MLF[MLflow :5000]
    API[FastAPI :8000]
    PROM[Prometheus :9090]
    GRAF[Grafana :3000]

    API -->|get_online_features| RD
    API -->|FeatureStore repo| FEAST
    API -->|load_model| MLF
    MLF --> PG
    MLF -->|artifacts| VOL[mlflow_artifacts]
    PROM -->|scrape /metrics| API
    GRAF -->|query| PROM
  end

  DEV[Developer] --> API
  DEV --> GRAF
  DEV --> MLF
```

### Prediction Request Flow

```mermaid
sequenceDiagram
  participant C as Client
  participant A as FastAPI
  participant F as Feast/Redis
  participant M as MLflow

  C->>A: POST /predict {entity_id}
  A->>F: get_online_features(cc_num)
  F-->>A: feature vector
  A->>M: load model, predict(features)
  M-->>A: prediction + probability
  A->>C: JSON response
```

### CI/CD Pipeline

```mermaid
flowchart LR
  subgraph GHA[GitHub Actions]
    TEST[pytest]
    BUILD[docker build + push to ECR]
    DEPLOY[ssh EC2 + docker-compose up]
    TEST --> BUILD --> DEPLOY
  end

  subgraph AWS
    ECR[ECR repository]
    EC2[EC2 instance]
    BUILD --> ECR
    DEPLOY --> EC2
  end
```

## Key Files

| File | Purpose |
|------|---------|
| `app/main.py` | FastAPI routes: `/health`, `/predict`, `/metrics` |
| `app/model_loader.py` | Loads model from MLflow registry |
| `app/feature_client.py` | Fetches features from Feast/Redis |
| `app/metrics.py` | Prometheus metrics definitions |
| `training/train.py` | Trains and registers model |
| `feast_repo/feature_store.yaml` | Feast configuration |
| `docker-compose.yml` | Local stack definition |
| `.github/workflows/deploy.yml` | CI/CD pipeline |
| `infrastructure/__main__.py` | Pulumi AWS infrastructure |

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `MLFLOW_TRACKING_URI` | http://localhost:5000 | MLflow server |
| `MODEL_NAME` | FraudDetector | Model in registry |
| `MODEL_STAGE` | Production | Stage to load |
| `FEAST_REPO_PATH` | ./feast_repo | Feast project path |
| `POSTGRES_USER` | mlflow | Database user |

## Alert Rules

| Alert | Condition |
|-------|-----------|
| ServiceDown | `up{job="fastapi"} == 0` for 1m |
| HighPredictionLatency | p95 > 1s for 5m |
| HighErrorRate | errors/requests > 5% for 2m |

## Related

- See **[SHOWCASE.md](../SHOWCASE.md)** for how-to-demo
- See **[diagrams/](diagrams/)** for exporting diagrams