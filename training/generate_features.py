# ============================================================================
# ModelServe — Generate Features for Feast
# ============================================================================
# Creates features.parquet from fraudTrain.csv for Feast ingestion.
# ============================================================================

import os
import logging
import pandas as pd
from datetime import datetime, timezone
from sklearn.preprocessing import LabelEncoder

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

DATA_PATH = os.getenv("DATA_PATH", "training/fraudTrain.csv")
OUT_PATH = "training/features.parquet"


def generate():
    """Generate features.parquet for Feast."""
    try:
        logger.info(f"Loading data from {DATA_PATH}")
        df = pd.read_csv(DATA_PATH)
        logger.info(f"Loaded {len(df)} rows")

        # Feature engineering
        le = LabelEncoder()
        df["category_enc"] = le.fit_transform(df["category"])
        logger.debug(f"Encoded categories: {len(le.classes_)} unique values")

        dt = pd.to_datetime(df["trans_date_trans_time"])
        df["trans_hour"] = dt.dt.hour
        df["trans_dow"] = dt.dt.dayofweek

        # Feast requires a timezone-aware event_timestamp
        df["event_timestamp"] = dt.dt.tz_localize("UTC")

        # Add created_at column (required by Feast FileSource)
        df["created_at"] = datetime.now(timezone.utc)

        # Select feature columns for Feast
        feast_cols = [
            "cc_num",           # entity key
            "event_timestamp",  # required by Feast
            "created_at",       # created timestamp column
            "amt",
            "category_enc",
            "trans_hour",
            "trans_dow",
            "city_pop",
            "merch_lat",
            "merch_long",
        ]
        feast_df = df[feast_cols].copy()

        # Get latest features per cc_num (for online store)
        feast_df = feast_df.sort_values("event_timestamp").drop_duplicates(
            subset=["cc_num"], keep="last"
        ).reset_index(drop=True)

        logger.info(f"Generated {len(feast_df)} unique features")

        # Write parquet
        feast_df.to_parquet(OUT_PATH, index=False)
        logger.info(f"Written features to {OUT_PATH}")

        print(f"\n=== Features Summary ===")
        print(f"Rows: {len(feast_df)}")
        print(f"Columns: {feast_df.columns.tolist()}")
        print(f"Sample cc_num values: {feast_df['cc_num'].head(3).tolist()}")

        return feast_df

    except FileNotFoundError as e:
        logger.error(f"Data file not found: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to generate features: {e}")
        raise


if __name__ == "__main__":
    generate()