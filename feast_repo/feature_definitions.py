# ============================================================================
# ModelServe — Feast Feature Definitions
# ============================================================================
# Defines Feast entities, data sources, and feature views.
# ============================================================================

from feast import Entity, FileSource, FeatureView, Field
from feast.value_type import ValueType
from feast.types import Float32, Float64, Int32, Int64
from datetime import timedelta


# ─────────────────────────────────────────────────────────────
#  Entity: Credit Card Number
# ─────────────────────────────────────────────────────────────

cc_num = Entity(
    name="cc_num",
    description="Credit card number (entity key)",
    value_type=ValueType.INT64,
)


# ─────────────────────────────────────────────────────────────
#  Data Source: features.parquet
# ─────────────────────────────────────────────────────────────

fraud_source = FileSource(
    name="fraud_source",
    path="../training/features.parquet",
    timestamp_field="event_timestamp",
    created_timestamp_column="created_at",
)


# ─────────────────────────────────────────────────────────────
#  Feature View: All features for fraud detection
# ─────────────────────────────────────────────────────────────

fraud_features = FeatureView(
    name="fraud_features",
    entities=[cc_num],
    ttl=timedelta(days=30),
    schema=[
        Field(name="amt", dtype=Float64, description="Transaction amount"),
        Field(name="category_enc", dtype=Int64, description="Encoded category"),
        Field(name="trans_hour", dtype=Int64, description="Transaction hour (0-23)"),
        Field(name="trans_dow", dtype=Int64, description="Day of week (0-6)"),
        Field(name="city_pop", dtype=Int64, description="City population"),
        Field(name="merch_lat", dtype=Float64, description="Merchant latitude"),
        Field(name="merch_long", dtype=Float64, description="Merchant longitude"),
    ],
    online=True,
    source=fraud_source,
    description="Fraud detection features for each credit card transaction",
)