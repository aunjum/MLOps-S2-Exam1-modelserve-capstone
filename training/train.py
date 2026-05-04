# ============================================================================
# ModelServe — Model Training Script
# ============================================================================
# TODO: Implement model training and MLflow registration.
#
# Dataset: https://www.kaggle.com/datasets/kartik2112/fraud-detection
#   - Use fraudTrain.csv (~1.3M rows, 22 features)
#   - Target column: is_fraud
#   - Entity key: cc_num
#   - Use class_weight='balanced' to handle class imbalance
#
# This script should:
#   1. Load fraudTrain.csv with pandas
#   2. Select and engineer features (15-20 features is enough)
#   3. Split into train/test sets (stratified on is_fraud)
#   4. Train a sklearn-compatible model (RandomForest, XGBoost, LightGBM)
#   5. Log to MLflow:
#      - Parameters: model type, hyperparameters, feature list
#      - Metrics: accuracy, precision, recall, f1, roc_auc
#      - The model artifact itself
#   6. Register the model in MLflow Model Registry
#   7. Transition the model version to "Production" stage
#   8. Export features.parquet (feature columns + cc_num + event_timestamp)
#      for Feast ingestion
#   9. Export sample_request.json with a valid entity_id for testing
#
# Prerequisites:
#   - MLflow and Postgres must be running (docker compose up postgres mlflow)
#   - fraudTrain.csv must be downloaded from Kaggle
#
# Usage:
#   python training/train.py
#
# IMPORTANT: This script must be reproducible — running it again should
# register a new model version with comparable metrics.
# Do NOT spend more than one session on model quality.
# A baseline AUC of 0.85+ is sufficient.
# ============================================================================

import os
import json
import pandas as pd
import numpy as np
import mlflow
import mlflow.sklearn
from mlflow import MlflowClient
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    f1_score, precision_score,
    recall_score, roc_auc_score,
    classification_report,
)
from sklearn.preprocessing import LabelEncoder

MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
MODEL_NAME          = "FraudDetector"
DATA_PATH           = os.getenv("DATA_PATH", "training/fraudTrain.csv")


def generate_sample_request(df: pd.DataFrame) -> None:
    """Write sample_request.json with a real fraud cc_num from the dataset."""
    fraud_cc = int(df[df["is_fraud"] == 1]["cc_num"].iloc[0])
    payload  = {"entity_id": fraud_cc}
    with open("training/sample_request.json", "w") as f:
        json.dump(payload, f, indent=2)
    count = int((df["cc_num"] == fraud_cc).sum())
    print(f"Written sample_request.json: entity_id={fraud_cc} ({count} txns)")


def load_and_engineer(path: str):
    """Load CSV, engineer features, return X, y, raw df, feature column list."""
    df = pd.read_csv(path)                    # uses the path parameter correctly

    # datetime features
    dt = pd.to_datetime(df["trans_date_trans_time"])
    df["trans_hour"] = dt.dt.hour
    df["trans_dow"]  = dt.dt.dayofweek

    # encode categorical
    le = LabelEncoder()
    df["category_enc"] = le.fit_transform(df["category"])

    feature_cols = [
        "amt", "category_enc", "trans_hour",
        "trans_dow", "city_pop", "merch_lat", "merch_long",
    ]
    X = df[feature_cols].fillna(0)
    y = df["is_fraud"]
    return X, y, df, feature_cols


def train():
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment("fraud-detection")

    X, y, df, feature_cols = load_and_engineer(DATA_PATH)  # passes path correctly

    # generate sample_request.json once (separate from feature engineering)
    generate_sample_request(df)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    params = {
        "n_estimators": 100,
        "max_depth":    10,
        "class_weight": "balanced",
        "random_state": 42,
        "n_jobs":       -1,
    }

    with mlflow.start_run(run_name="baseline-rf") as run:
        model = RandomForestClassifier(**params)
        model.fit(X_train, y_train)

        y_pred = model.predict(X_test)
        y_prob = model.predict_proba(X_test)[:, 1]

        metrics = {
            "f1":        round(f1_score(y_test, y_pred), 4),
            "precision": round(precision_score(y_test, y_pred), 4),
            "recall":    round(recall_score(y_test, y_pred), 4),
            "roc_auc":   round(roc_auc_score(y_test, y_prob), 4),
        }

        mlflow.log_params(params)
        mlflow.log_params({"feature_cols": str(feature_cols)})
        mlflow.log_metrics(metrics)

        mlflow.sklearn.log_model(
            sk_model=model,
            artifact_path="model",
            registered_model_name=MODEL_NAME,
        )

        print(f"\nRun ID : {run.info.run_id}")
        print(f"Metrics: {metrics}")
        print(classification_report(
            y_test, y_pred,
            target_names=["legit", "fraud"]
        ))

    # promote latest version → Production
    client  = MlflowClient()
    version = client.get_latest_versions(
        MODEL_NAME, stages=["None"]
    )[0].version

    client.transition_model_version_stage(
        name=MODEL_NAME,
        version=version,
        stage="Production",
        archive_existing_versions=True,
    )
    print(f"\nModel '{MODEL_NAME}' v{version} → Production")


if __name__ == "__main__":
    train()