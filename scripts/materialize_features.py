#!/usr/bin/env python3
# ============================================================================
# ModelServe — Feast Feature Materialization Script
# ============================================================================
# Materializes features from the offline store to the Redis online store.
#
# Usage (from docker container):
#   docker compose exec fastapi python scripts/materialize_features.py
#
# Or from host (requires localhost:6379 for Redis):
#   python scripts/materialize_features.py
# ============================================================================

import os
import sys
import logging
from datetime import datetime, timezone

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def materialize_features():
    """Materialize features to Redis online store."""
    try:
        from feast import FeatureStore

        # Determine repo path
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # Go up from scripts/ to project root
        repo_path = os.path.join(script_dir, "feast_repo")

        logger.info(f"Loading Feast store from: {repo_path}")
        store = FeatureStore(repo_path=repo_path)

        # Materialize to current time
        end_time = datetime.now(timezone.utc)
        start_time = datetime(2025, 1, 1, tzinfo=timezone.utc)

        logger.info(f"Materializing features from {start_time} to {end_time}")
        store.materialize(start_time, end_time)

        logger.info("Feature materialization complete!")
        return True

    except Exception as e:
        logger.error(f"Feature materialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = materialize_features()
    sys.exit(0 if success else 1)