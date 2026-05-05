# ============================================================================
# ModelServe — Model Training Script
# ============================================================================
# Trains fraud detection model and registers in MLflow.
# ============================================================================

import os
import sys
import json
import logging
import pandas as pd
import numpy as np
import mlflow
import mlflow.sklearn
from datetime import datetime, timezone
from mlflow import MlflowClient
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    f1_score, precision_score,
    recall_score, roc_auc_score,
    classification_report,
)
from sklearn.preprocessing import LabelEncoder

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
MODEL_NAME = "FraudDetector"
DATA_PATH = os.getenv("DATA_PATH", "training/fraudTrain.csv")


def generate_features_parquet(df: pd.DataFrame) -> None:
    """Generate features.parquet for Feast."""
    try:
        # Add required timestamp columns
        df["event_timestamp"] = pd.to_datetime(
            df["trans_date_trans_time"]
        ).dt.tz_localize("UTC")
        df["created_at"] = datetime.now(timezone.utc)

        # Select features for Feast
        feast_cols = [
            "cc_num",
            "event_timestamp",
            "created_at",
            "amt",
            "category_enc",
            "trans_hour",
            "trans_dow",
            "city_pop",
            "merch_lat",
            "merch_long",
        ]

        # Get latest features per cc_num
        feast_df = df[feast_cols].sort_values("event_timestamp").drop_duplicates(
            subset=["cc_num"], keep="last"
        ).reset_index(drop=True)

        out_path = "training/features.parquet"
        feast_df.to_parquet(out_path, index=False)
        logger.info(f"Written features.parquet: {len(feast_df)} rows")

    except Exception as e:
        logger.error(f"Failed to generate features.parquet: {e}")
        raise


def generate_sample_request(df: pd.DataFrame) -> None:
    """Write sample_request.json with a real fraud cc_num from the dataset."""
    try:
        fraud_cc = int(df[df["is_fraud"] == 1]["cc_num"].iloc[0])
        payload = {"entity_id": fraud_cc}
        out_path = "training/sample_request.json"
        with open(out_path, "w") as f:
            json.dump(payload, f, indent=2)
        count = int((df["cc_num"] == fraud_cc).sum())
        logger.info(f"Written sample_request.json: entity_id={fraud_cc} ({count} txns)")
    except Exception as e:
        logger.error(f"Failed to generate sample_request.json: {e}")
        raise


def load_and_engineer(path: str):
    """Load CSV, engineer features, return X, y, raw df, feature column list."""
    logger.info(f"Loading data from {path}")
    df = pd.read_csv(path)
    logger.info(f"Loaded {len(df)} rows")

    # datetime features
    dt = pd.to_datetime(df["trans_date_trans_time"])
    df["trans_hour"] = dt.dt.hour
    df["trans_dow"] = dt.dt.dayofweek

    # encode categorical
    le = LabelEncoder()
    df["category_enc"] = le.fit_transform(df["category"])
    logger.debug(f"Encoded categories: {len(le.classes_)} unique")

    feature_cols = [
        "amt", "category_enc", "trans_hour",
        "trans_dow", "city_pop", "merch_lat", "merch_long",
    ]
    X = df[feature_cols].fillna(0)
    y = df["is_fraud"]
    logger.info(f"Features: {feature_cols}")
    return X, y, df, feature_cols


def train():
    """Main training function."""
    logger.info("Starting model training...")

    # Connect to MLflow
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment("fraud-detection")
    logger.info(f"MLflow tracking: {MLFLOW_TRACKING_URI}")

    # Load and engineer features
    X, y, df, feature_cols = load_and_engineer(DATA_PATH)

    # Generate features.parquet for Feast
    generate_features_parquet(df)

    # Generate sample_request.json
    generate_sample_request(df)

    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    logger.info(f"Train: {len(X_train)}, Test: {len(X_test)}")

    # Model parameters
    params = {
        "n_estimators": 100,
        "max_depth": 10,
        "class_weight": "balanced",
        "random_state": 42,
        "n_jobs": -1,
    }
    logger.info(f"Model params: {params}")

    # Train model with MLflow tracking
    with mlflow.start_run(run_name="baseline-rf") as run:
        logger.info("Training RandomForest model...")
        model = RandomForestClassifier(**params)
        model.fit(X_train, y_train)

        # Evaluate
        y_pred = model.predict(X_test)
        y_prob = model.predict_proba(X_test)[:, 1]

        metrics = {
            "f1": round(f1_score(y_test, y_pred), 4),
            "precision": round(precision_score(y_test, y_pred), 4),
            "recall": round(recall_score(y_test, y_pred), 4),
            "roc_auc": round(roc_auc_score(y_test, y_prob), 4),
        }

        # Log to MLflow
        mlflow.log_params(params)
        mlflow.log_params({"feature_cols": str(feature_cols)})
        mlflow.log_metrics(metrics)

        # Register model
        mlflow.sklearn.log_model(
            sk_model=model,
            artifact_path="model",
            registered_model_name=MODEL_NAME,
        )

        logger.info(f"\nRun ID: {run.info.run_id}")
        logger.info(f"Metrics: {metrics}")
        print(classification_report(y_test, y_pred, target_names=["legit", "fraud"]))

    # Promote to Production stage
    try:
        client = MlflowClient()
        versions = client.get_latest_versions(MODEL_NAME, stages=["None"])
        if not versions:
            raise ValueError("No model versions found")

        version = versions[0].version
        client.transition_model_version_stage(
            name=MODEL_NAME,
            version=version,
            stage="Production",
            archive_existing_versions=True,
        )
        logger.info(f"Model '{MODEL_NAME}' v{version} -> Production")
    except Exception as e:
        logger.error(f"Failed to promote model to Production: {e}")
        raise

    logger.info("Training complete!")


if __name__ == "__main__":
    try:
        train()
    except Exception as e:
        logger.error(f"Training failed: {e}")
        sys.exit(1)