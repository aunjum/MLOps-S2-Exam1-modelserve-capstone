# Known Issues and Troubleshooting

## Issues Found During Testing

### 1. Grafana Port 3001 Connection Refused

**Status:** 🔴 Not Fully Working

**Issue:** Grafana container is running but port 3001 returns connection refused from host.

**Symptoms:**
```bash
$ curl http://localhost:3001/api/health
curl: (56) Recv failure: Connection reset by peer
```

**Container Status:**
```
modelserve-grafana   grafana/grafana:10.4.3   Running (healthy)   3000/tcp, 0.0.0.0:3001->3001/tcp
```

**Workaround:** Access Grafana from inside the container:
```bash
docker exec modelserve-grafana curl http://localhost:3000/login
```

**Root Cause:** Possibly a Grafana configuration issue or networking problem between host and container.

---

### 2. Model Returns Probability 0.0

**Status:** 🟡 Low Severity

**Issue:** Prediction returns `"probability": 0.0` instead of actual probability.

**Root Cause:** The MLflow pyfunc model wrapper doesn't expose `predict_proba` method directly.

**Error Log:**
```
app.model_loader - ERROR - Prediction failed: 'PyFuncModel' object has no attribute 'predict_proba'
```

**Workaround:** The code falls back to returning probability 0.0 when `predict_proba` fails. The prediction itself works correctly.

**Fix:** Modify `app/model_loader.py` to extract probability from raw model or use a different model loading approach.

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

**Status:** 🟡 Low Severity

**Issue:** Model may not load on first startup if MLflow container is still initializing.

**Symptoms:**
```
app.main - WARNING - Model not loaded - predictions will fail
```

**Workaround:** Restart FastAPI after MLflow is fully healthy:
```bash
docker restart modelserve-fastapi
```

**Fix:** Add a startup delay or retry logic in the model loader.

---

### 5. MLflow Container Health Check

**Status:** 🟡 Informational

**Issue:** MLflow container shows as "unhealthy" even though it's functional.

**Container Status:**
```
modelserve-mlflow   ghcr.io/mlflow/mlflow:v2.12.2   Running (unhealthy)   5000/tcp
```

**Details:** The health check uses `curl http://localhost:5000/` which returns HTML instead of JSON, causing health check to fail despite MLflow working.

**Impact:** None - MLflow is fully functional.

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

# Restart FastAPI (fixes model loading timing)
docker restart modelserve-fastapi

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
curl http://localhost:5000/health
curl http://localhost:9090/-/healthy
redis-cli ping
```

---

*Last updated: 2026-05-07*