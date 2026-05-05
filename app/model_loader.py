# ============================================================================
# ModelServe — MLflow Model Loader
# ============================================================================
# Implements model loading from MLflow Model Registry.
# ============================================================================

import os
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Try to import mlflow
try:
    import mlflow
    MLFLOW_AVAILABLE = True
except ImportError as e:
    logger.warning(f"MLflow not available: {e}")
    MLFLOW_AVAILABLE = False


class ModelLoader:
    """Loads and manages the MLflow model for inference."""

    def __init__(
        self,
        tracking_uri: Optional[str] = None,
        model_name: Optional[str] = None,
        model_stage: Optional[str] = None,
    ):
        """Initialize the model loader.

        Args:
            tracking_uri: MLflow tracking server URI. Defaults to MLFLOW_TRACKING_URI env var.
            model_name: Name of the model in MLflow Registry. Defaults to MODEL_NAME env var.
            model_stage: Stage to load (e.g., "Production"). Defaults to MODEL_STAGE env var.
        """
        self.tracking_uri = tracking_uri or os.getenv(
            "MLFLOW_TRACKING_URI", "http://localhost:5000"
        )
        self.model_name = model_name or os.getenv("MODEL_NAME", "FraudDetector")
        self.model_stage = model_stage or os.getenv("MODEL_STAGE", "Production")

        self.model = None
        self.model_version = None

    def load(self) -> bool:
        """Load the model from MLflow Registry.

        Returns:
            True if model loaded successfully, False otherwise.
        """
        if not MLFLOW_AVAILABLE:
            logger.error("MLflow is not available")
            return False

        try:
            # Set tracking URI
            mlflow.set_tracking_uri(self.tracking_uri)
            logger.info(f"MLflow tracking URI: {self.tracking_uri}")

            # Construct model URI
            model_uri = f"models:/{self.model_name}/{self.model_stage}"
            logger.info(f"Loading model from: {model_uri}")

            # Load the model
            self.model = mlflow.pyfunc.load_model(model_uri)

            # Get model version
            self.model_version = self._get_model_version()
            logger.info(f"Model loaded successfully. Version: {self.model_version}")

            return True

        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            self.model = None
            return False

    def _get_model_version(self) -> str:
        """Get the model version string from MLflow."""
        if not MLFLOW_AVAILABLE:
            return "unknown"

        try:
            from mlflow import MlflowClient
            client = MlflowClient()
            versions = client.get_latest_versions(self.model_name, stages=[self.model_stage])
            if versions:
                return str(versions[0].version)
        except Exception as e:
            logger.warning(f"Could not get model version: {e}")

        return "unknown"

    def predict(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Run inference on feature inputs.

        Args:
            features: Dictionary of feature values.

        Returns:
            Dictionary with prediction and probability.
        """
        if self.model is None:
            logger.error("Model not loaded, cannot predict")
            return {"prediction": 0, "probability": 0.0}

        try:
            # Convert features to DataFrame for sklearn
            import pandas as pd
            feature_df = pd.DataFrame([features])

            # Ensure correct column order
            expected_cols = [
                "amt", "category_enc", "trans_hour",
                "trans_dow", "city_pop", "merch_lat", "merch_long"
            ]
            # Reorder columns, fill missing with 0
            for col in expected_cols:
                if col not in feature_df.columns:
                    feature_df[col] = 0
            feature_df = feature_df[expected_cols]

            # Run prediction
            pred = self.model.predict(feature_df)[0]
            prob = self.model.predict_proba(feature_df)[0][1]

            return {
                "prediction": int(pred),
                "probability": float(prob),
            }

        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            return {"prediction": 0, "probability": 0.0}

    def is_loaded(self) -> bool:
        """Check if model is loaded."""
        return self.model is not None


# Global instance
_model_loader: Optional[ModelLoader] = None


def get_model_loader() -> ModelLoader:
    """Get or create the global ModelLoader instance."""
    global _model_loader
    if _model_loader is None:
        _model_loader = ModelLoader()
    return _model_loader