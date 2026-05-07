# ============================================================================
# ModelServe — MLflow Model Loader
# ============================================================================
# Implements model loading from MLflow Model Registry.
# Falls back to local model if MLflow is not available.
# ============================================================================

import os
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Try to import mlflow
try:
    import mlflow
    MLFLOW_AVAILABLE = True
except ImportError as e:
    logger.warning(f"MLflow not available: {e}")
    MLFLOW_AVAILABLE = False

# Try to import sklearn
try:
    import sklearn
    from sklearn.ensemble import RandomForestClassifier
    SKLEARN_AVAILABLE = True
except ImportError as e:
    logger.warning(f"sklearn not available: {e}")
    SKLEARN_AVAILABLE = False


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
        """Load the model from MLflow Registry or local fallback.

        Returns:
            True if model loaded successfully, False otherwise.
        """
        # Try MLflow first
        if MLFLOW_AVAILABLE:
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
                logger.warning(f"MLflow loading failed: {e}")

        # Fallback: try loading local model
        return self._load_local_model()

    def _load_local_model(self) -> bool:
        """Load a local model as fallback."""
        if not SKLEARN_AVAILABLE:
            logger.error("sklearn is not available")
            return False

        # Try common local model paths
        local_paths = [
            "training/model.pkl",
            "model.pkl",
            "./model.pkl",
            os.path.join(os.path.dirname(__file__), "..", "training", "model.pkl"),
        ]

        for path in local_paths:
            try:
                if os.path.exists(path):
                    import pickle
                    with open(path, "rb") as f:
                        self.model = pickle.load(f)
                    self.model_version = "local"
                    logger.info(f"Loaded local model from: {path}")
                    return True
            except Exception as e:
                logger.debug(f"Failed to load {path}: {e}")

        # No local model found - create a simple dummy model for testing
        logger.warning("No model found. Creating dummy model for testing.")
        return self._create_dummy_model()

    def _create_dummy_model(self) -> bool:
        """Create a simple dummy model for testing purposes."""
        if not SKLEARN_AVAILABLE:
            return False

        try:
            # Create a simple RandomForest with default params
            self.model = RandomForestClassifier(
                n_estimators=10,
                max_depth=5,
                random_state=42,
            )
            # Train on dummy data so it can predict
            import numpy as np
            X_dummy = np.random.rand(100, 7)
            y_dummy = np.random.randint(0, 2, 100)
            self.model.fit(X_dummy, y_dummy)
            self.model_version = "dummy"
            logger.info("Created dummy model for testing")
            return True
        except Exception as e:
            logger.error(f"Failed to create dummy model: {e}")
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

            # Check if it's an MLflow pyfunc model or raw sklearn model
            if hasattr(self.model, "predict"):
                # MLflow pyfunc or sklearn model
                pred = self.model.predict(feature_df)[0]

                # Try predict_proba, handle both formats
                prob = 0.0
                try:
                    # Try direct predict_proba first
                    if hasattr(self.model, "predict_proba"):
                        proba = self.model.predict_proba(feature_df)[0]
                    else:
                        # Try to get underlying model from pyfunc
                        raise AttributeError("No predict_proba")
                except AttributeError:
                    try:
                        # Try to extract underlying sklearn model from pyfunc
                        if hasattr(self.model, "model"):
                            proba = self.model.model.predict_proba(feature_df)[0]
                        elif hasattr(self.model, "predict_proba"):
                            proba = self.model.predict_proba(feature_df)[0]
                        else:
                            raise
                except Exception:
                    # Fallback: use prediction as probability
                    prob = 1.0 if pred == 1 else 0.0
                else:
                    # Handle both binary and multiclass
                    if proba.ndim > 1:
                        prob = proba[1]  # Class 1 probability for binary
                    else:
                        prob = proba[0]

                return {
                    "prediction": int(pred),
                    "probability": float(prob),
                }

            return {"prediction": 0, "probability": 0.0}

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