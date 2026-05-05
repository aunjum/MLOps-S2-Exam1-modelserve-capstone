# ============================================================================
# ModelServe — Feast Feature Client
# ============================================================================
# Implements feature fetching from the Feast online store.
# ============================================================================

import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Try to import feast, handle if not available
try:
    from feast import FeatureStore
    FEAST_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Feast not available: {e}")
    FEAST_AVAILABLE = False


class FeatureClient:
    """Client for fetching features from Feast online store."""

    def __init__(self, repo_path: Optional[str] = None):
        """Initialize the Feast FeatureStore client.

        Args:
            repo_path: Path to the Feast repository. Defaults to FEAST_REPO_PATH env var.
        """
        self.repo_path = repo_path or os.getenv("FEAST_REPO_PATH", "./feast_repo")
        self.store = None

        if not FEAST_AVAILABLE:
            logger.warning("Feast is not installed. FeatureClient will not function.")
            return

        try:
            self.store = FeatureStore(repo_path=self.repo_path)
            logger.info(f"Initialized Feast FeatureStore at: {self.repo_path}")
        except Exception as e:
            logger.error(f"Failed to initialize Feast FeatureStore: {e}")
            self.store = None

    def get_features(self, entity_id: int) -> Optional[Dict[str, Any]]:
        """Fetch features for a given entity from the Feast online store.

        Args:
            entity_id: The credit card number (cc_num) to fetch features for.

        Returns:
            Dictionary of feature values, or None if lookup fails.
        """
        if self.store is None:
            logger.error("Feast store not initialized")
            return self._get_default_features()

        try:
            entity_rows = [{"cc_num": entity_id}]
            online_features = self.store.get_online_features(
                features=["fraud_features:amt", "fraud_features:category_enc",
                         "fraud_features:trans_hour", "fraud_features:trans_dow",
                         "fraud_features:city_pop", "fraud_features:merch_lat",
                         "fraud_features:merch_long"],
                entity_rows=entity_rows,
            )

            # Convert to dict
            feature_dict = online_features.to_dict()

            if feature_dict and feature_dict.get("cc_num"):
                logger.info(f"Successfully fetched features for entity_id={entity_id}")
                return self._flatten_features(feature_dict)
            else:
                logger.warning(f"No features found for entity_id={entity_id}")
                return self._get_default_features()

        except Exception as e:
            logger.error(f"Error fetching features for entity_id={entity_id}: {e}")
            return self._get_default_features()

    def _flatten_features(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Flatten Feast feature response to simple dict."""
        try:
            result = {}
            # Extract feature values from the nested structure
            for key, value in features.items():
                if key == "cc_num":
                    continue
                if isinstance(value, list) and len(value) > 0:
                    result[key] = value[0]
                else:
                    result[key] = value
            return result
        except Exception as e:
            logger.error(f"Error flattening features: {e}")
            return features

    def _get_default_features(self) -> Dict[str, float]:
        """Return default feature values when lookup fails."""
        return {
            "amt": 0.0,
            "category_enc": 0,
            "trans_hour": 0,
            "trans_dow": 0,
            "city_pop": 0,
            "merch_lat": 0.0,
            "merch_long": 0.0,
        }


# Global instance
_feature_client: Optional[FeatureClient] = None


def get_feature_client() -> FeatureClient:
    """Get or create the global FeatureClient instance."""
    global _feature_client
    if _feature_client is None:
        _feature_client = FeatureClient()
    return _feature_client