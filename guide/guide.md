# Guide

Simple reference for commands and workflows.

## Quick Start

```bash
# Start everything
docker compose up -d

# Materialize features
docker compose exec -T fastapi /bin/bash -c "cd /app/feast_repo && feast materialize-incremental \$(date -u +%Y-%m-%dT%H:%M:%S)"

# Test
curl http://localhost:8000/health
curl -X POST http://localhost:8000/predict -H "Content-Type: application/json" -d '{"entity_id": 340187018810220}'
```

## Services

| Service | Port | URL |
|---------|------|-----|
| FastAPI | 8000 | http://localhost:8000 |
| MLflow | 5000 | http://localhost:5000 |
| Prometheus | 9090 | http://localhost:9090 |
| Grafana | 3000 | admin/admin |

## Train Model

```bash
source mlops_venv/bin/activate
python training/train.py
```

## AWS Deploy

```bash
cd infrastructure
pulumi up
```

## Debug

```bash
docker compose logs -f fastapi
docker compose restart fastapi
```