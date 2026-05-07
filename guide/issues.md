# Known Issues and Troubleshooting

## Issues Found During Testing

### 1. Grafana Port 3001 Connection Refused

**Status:** ✅ Fixed

**Issue:** Grafana container was running but port 3001 returned connection refused from host.

**Root Cause:** Port mapping was `3001:3001` but Grafana inside container listens on port 3000.

**Fix:** Changed port mapping to `3001:3000` in docker-compose.yml.

---

### 2. Model Returns Probability 0.0

**Status:** ✅ Fixed

**Issue:** Prediction returned `"probability": 0.0` instead of actual probability.

**Root Cause:** The MLflow pyfunc model wrapper doesn't expose `predict_proba` method directly.

**Fix:** Modified `app/model_loader.py` to extract probability from underlying model (`model.model`). Now properly returns probability from pyfunc-wrapped sklearn models.

---

### 3. Feast Feature Store Configuration

**Status:** ✅ Fixed

**Issue:** Feast couldn't materialize features from host machine due to Redis connection string.

**Details:**
- Host config used `localhost:6379`
- Docker container needs `redis:6379` (Docker network)

**Fix:** Keep `redis:6379` in `feast_repo/feature_store.yaml` for container use. Materialize from inside the container:
```bash
docker exec modelserve-fastapi python -c "
from feast import FeatureStore
from datetime import datetime, timezone
fs = FeatureStore(repo_path='/app/feast_repo')
fs.materialize(start_date=datetime(2024,1,1,tzinfo=timezone.utc), end_date=datetime.now(timezone.utc))
"
```

---

### 4. FastAPI Model Loading Timing

**Status:** ✅ Fixed

**Issue:** Model may not load on first startup if MLflow container is still initializing.

**Fix:** Added retry logic (5 retries with 3s delay) in `app/main.py` startup event to wait for MLflow to become available.

---

### 5. MLflow Container Health Check

**Status:** ✅ Fixed

**Issue:** MLflow container showed as "unhealthy" even though it was functional.

**Details:** The health check used `curl -f` which failed on HTTP errors.

**Fix:** Changed health check to use `curl -sf` to not fail on HTTP status codes.

---

### 6. Grafana Database Lock

**Status:** 🟡 Informational

**Issue:** Grafana logs show intermittent database lock warnings.

**Log Sample:**
```
logger=sqlstore.transactions level=info msg="Database locked, sleeping then retrying" error="database is locked" retry=0 code="database is locked"
```

**Impact:** Low - Grafana continues to operate normally.

---

## Deprecation Warnings

The following deprecation warnings appear in logs but don't affect functionality:

1. **FastAPI `on_event` deprecated** - Use lifespan event handlers instead
2. **MLflow stages deprecated** - Model Registry stages will be removed in future release
3. **Pydantic V1 validators** - Should migrate to V2 style validators
4. **Feast serialization version** - Should use version 3

---

## Quick Troubleshooting Commands

```bash
# Check all containers
docker ps

# View FastAPI logs
docker logs modelserve-fastapi --tail 50

# Materialize features
docker exec modelserve-fastapi python -c "
from feast import FeatureStore
from datetime import datetime, timezone
fs = FeatureStore(repo_path='/app/feast_repo')
fs.materialize(start_date=datetime(2024,1,1,tzinfo=timezone.utc), end_date=datetime.now(timezone.utc))
"

# Test endpoints
curl http://localhost:8000/health
curl -X POST http://localhost:8000/predict -H "Content-Type: application/json" -d '{"entity_id": 340187018810220}'
curl http://localhost:5000/
curl http://localhost:9090/-/healthy
redis-cli ping
```

---

*Last updated: 2026-05-07*