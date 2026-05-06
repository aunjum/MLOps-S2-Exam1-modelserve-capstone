# Documentation

## Quick Links

- **[SHOWCASE.md](../SHOWCASE.md)** — How the system works (start here)
- **[ARCHITECTURE.md](ARCHITECTURE.md)** — Technical details, diagrams, decisions
- **[diagrams/](diagrams/)** — Export diagrams to PNG/SVG

## What You Need to Know

1. **Training** (`training/train.py`) — Trains model, registers to MLflow
2. **Features** (`feast_repo/`) — Feast + Redis for fast feature lookups
3. **API** (`app/main.py`) — FastAPI serves predictions
4. **Monitoring** (`monitoring/`) — Prometheus + Grafana
5. **Deploy** (`.github/workflows/deploy.yml`) — CI/CD to AWS EC2