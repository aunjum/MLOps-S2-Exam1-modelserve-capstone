import os
import pandas as pd
from sklearn.preprocessing import LabelEncoder

DATA_PATH = os.getenv("DATA_PATH", "training/fraudTrain.csv")
OUT_PATH  = "training/features.parquet"


def generate():
    df = pd.read_csv(DATA_PATH)

    le = LabelEncoder()
    df["category_enc"] = le.fit_transform(df["category"])

    dt = pd.to_datetime(df["trans_date_trans_time"])
    df["trans_hour"] = dt.dt.hour
    df["trans_dow"]  = dt.dt.dayofweek

    # Feast requires a timezone-aware event_timestamp
    df["event_timestamp"] = dt.dt.tz_localize("UTC")

    feast_df = df[[
        "cc_num",           # entity key — must match feature_store entity
        "event_timestamp",  # required by Feast
        "amt",
        "category_enc",
        "trans_hour",
        "trans_dow",
        "city_pop",
        "merch_lat",
        "merch_long",
    ]].drop_duplicates(subset=["cc_num"], keep="last").reset_index(drop=True)

    feast_df.to_parquet(OUT_PATH, index=False)

    print(f"Written {len(feast_df)} rows → {OUT_PATH}")
    print(f"Columns : {feast_df.columns.tolist()}")
    print(f"Sample cc_num values: {feast_df['cc_num'].head(3).tolist()}")


if __name__ == "__main__":
    generate()