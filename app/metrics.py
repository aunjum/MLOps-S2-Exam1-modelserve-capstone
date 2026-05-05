# ============================================================================
# ModelServe — Prometheus Metrics
# ============================================================================
# Defines Prometheus metrics for the inference service.
# ============================================================================

import logging
from prometheus_client import Counter, Histogram, Gauge

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
#  Metrics Definitions
# ─────────────────────────────────────────────────────────────

# Total number of prediction requests received
prediction_requests_total = Counter(
    "prediction_requests_total",
    "Total number of prediction requests received",
)

# Time taken to process each prediction (feature fetch + model inference)
prediction_duration_seconds = Histogram(
    "prediction_duration_seconds",
    "Time taken to process each prediction",
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# Number of failed prediction requests
prediction_errors_total = Counter(
    "prediction_errors_total",
    "Number of failed prediction requests",
)

# Currently served model version — set once on startup
model_version_info = Gauge(
    "model_version_info",
    "Currently served model version",
    ["version"],
)

# Successful feature lookups from Feast
feast_online_store_hits_total = Counter(
    "feast_online_store_hits_total",
    "Successful feature lookups from Feast",
)

# Failed or empty feature lookups from Feast
feast_online_store_misses_total = Counter(
    "feast_online_store_misses_total",
    "Failed or empty feature lookups from Feast",
)


def record_prediction(duration: float) -> None:
    """Record a successful prediction with its duration."""
    try:
        prediction_requests_total.inc()
        prediction_duration_seconds.observe(duration)
        logger.debug(f"Recorded prediction: duration={duration:.4f}s")
    except Exception as e:
        logger.error(f"Failed to record prediction metric: {e}")


def record_prediction_error() -> None:
    """Record a failed prediction request."""
    try:
        prediction_errors_total.inc()
        logger.warning("Recorded prediction error")
    except Exception as e:
        logger.error(f"Failed to record prediction error metric: {e}")


def record_feast_hit() -> None:
    """Record a successful Feast feature lookup."""
    try:
        feast_online_store_hits_total.inc()
        logger.debug("Recorded Feast hit")
    except Exception as e:
        logger.error(f"Failed to record Feast hit metric: {e}")


def record_feast_miss() -> None:
    """Record a failed Feast feature lookup."""
    try:
        feast_online_store_misses_total.inc()
        logger.warning("Recorded Feast miss")
    except Exception as e:
        logger.error(f"Failed to record Feast miss metric: {e}")


def set_model_version(version: str) -> None:
    """Set the currently served model version."""
    try:
        model_version_info.labels(version=version).set(1)
        logger.info(f"Model version set: {version}")
    except Exception as e:
        logger.error(f"Failed to set model version metric: {e}")