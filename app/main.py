# ============================================================================
# ModelServe — FastAPI Inference Service
# ============================================================================
# Implements the inference service with all required endpoints.
# ============================================================================

import os
import logging
import time
from datetime import datetime
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Query, Response
from pydantic import BaseModel, Field
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from app.model_loader import get_model_loader
from app.feature_client import get_feature_client
from app import metrics

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
#  FastAPI App
# ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="ModelServe - Fraud Detection API",
    description="MLOps capstone: fraud detection inference service",
    version="1.0.0",
)


# ─────────────────────────────────────────────────────────────
#  Request/Response Models
# ─────────────────────────────────────────────────────────────

class PredictRequest(BaseModel):
    """Request body for /predict endpoint."""
    entity_id: int = Field(..., description="Credit card number (cc_num)")


class PredictResponse(BaseModel):
    """Response body for /predict endpoint."""
    prediction: int
    probability: float
    model_version: str
    timestamp: str
    features: Optional[Dict[str, Any]] = None


class HealthResponse(BaseModel):
    """Response body for /health endpoint."""
    status: str
    model_version: str


# ─────────────────────────────────────────────────────────────
#  Lifespan Events
# ─────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    """Load model on startup."""
    logger.info("Starting ModelServe API...")

    # Retry logic for MLflow timing issue
    max_retries = 5
    retry_delay = 3

    for attempt in range(max_retries):
        try:
            model_loader = get_model_loader()
            success = model_loader.load()

            if success and model_loader.model_version:
                metrics.set_model_version(model_loader.model_version)
                logger.info(f"Model loaded: version={model_loader.model_version}")
                break
            else:
                if attempt < max_retries - 1:
                    logger.warning(f"Model not loaded, retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)
                else:
                    logger.warning("Model not loaded after retries - predictions may fail")
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"Startup error: {e}, retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(retry_delay)
            else:
                logger.error(f"Startup failed after {max_retries} attempts: {e}")


# ─────────────────────────────────────────────────────────────
#  Endpoints
# ─────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint.

    Returns:
        Health status and model version.
    """
    try:
        model_loader = get_model_loader()
        version = model_loader.model_version or "not_loaded"

        return HealthResponse(
            status="healthy",
            model_version=version,
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/predict", response_model=PredictResponse)
async def predict(request: PredictRequest):
    """Make a fraud prediction for a given entity.

    Args:
        request: PredictRequest with entity_id.

    Returns:
        Prediction result with probability and metadata.
    """
    start_time = time.time()

    try:
        # Get features from Feast
        feature_client = get_feature_client()
        features = feature_client.get_features(request.entity_id)

        if features is None:
            metrics.record_feast_miss()
            raise HTTPException(
                status_code=404,
                detail=f"No features found for entity_id={request.entity_id}",
            )

        metrics.record_feast_hit()

        # Get model and predict
        model_loader = get_model_loader()

        if not model_loader.is_loaded():
            metrics.record_prediction_error()
            raise HTTPException(
                status_code=503,
                detail="Model not loaded",
            )

        result = model_loader.predict(features)

        # Record metrics
        duration = time.time() - start_time
        metrics.record_prediction(duration)

        logger.info(
            f"Prediction: entity_id={request.entity_id}, "
            f"prediction={result['prediction']}, prob={result['probability']:.4f}"
        )

        return PredictResponse(
            prediction=result["prediction"],
            probability=result["probability"],
            model_version=model_loader.model_version or "unknown",
            timestamp=datetime.utcnow().isoformat() + "Z",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        metrics.record_prediction_error()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/predict/{entity_id}", response_model=PredictResponse)
async def predict_with_explain(
    entity_id: int,
    explain: bool = Query(False, description="Include feature values in response"),
):
    """Make a fraud prediction with optional explanation.

    Args:
        entity_id: Credit card number (cc_num).
        explain: If true, include feature values in response.

    Returns:
        Prediction result with optional feature explanation.
    """
    start_time = time.time()

    try:
        # Get features from Feast
        feature_client = get_feature_client()
        features = feature_client.get_features(entity_id)

        if features is None:
            metrics.record_feast_miss()
            raise HTTPException(
                status_code=404,
                detail=f"No features found for entity_id={entity_id}",
            )

        metrics.record_feast_hit()

        # Get model and predict
        model_loader = get_model_loader()

        if not model_loader.is_loaded():
            metrics.record_prediction_error()
            raise HTTPException(
                status_code=503,
                detail="Model not loaded",
            )

        result = model_loader.predict(features)

        # Record metrics
        duration = time.time() - start_time
        metrics.record_prediction(duration)

        logger.info(
            f"Prediction (explain={explain}): entity_id={entity_id}, "
            f"prediction={result['prediction']}, prob={result['probability']:.4f}"
        )

        return PredictResponse(
            prediction=result["prediction"],
            probability=result["probability"],
            model_version=model_loader.model_version or "unknown",
            timestamp=datetime.utcnow().isoformat() + "Z",
            features=features if explain else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        metrics.record_prediction_error()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics")
async def prometheus_metrics():
    """Expose Prometheus metrics.

    Returns:
        Prometheus metrics in text format.
    """
    try:
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST,
        )
    except Exception as e:
        logger.error(f"Failed to generate metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────
#  Root
# ─────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "ModelServe - Fraud Detection API",
        "version": "1.0.0",
        "endpoints": ["/health", "/predict", "/predict/{entity_id}", "/metrics"],
    }