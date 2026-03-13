from __future__ import annotations

import argparse
from datetime import datetime

import pandas as pd
from google.cloud import bigquery


def _parse_ts(x: object) -> object:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    s = str(x).strip()
    if not s:
        return None
    # BigQuery client accepts datetime objects; keep it simple.
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--project", required=True)
    p.add_argument("--dataset", required=True)
    p.add_argument("--table", default="raw_tweets")
    p.add_argument("--csv", required=True)
    p.add_argument("--source", default="humaid")
    args = p.parse_args()

    df = pd.read_csv(args.csv)
    for col in ["tweet_id", "text", "label", "event", "created_at"]:
        if col not in df.columns:
            df[col] = None

    df["tweet_id"] = df["tweet_id"].fillna("").astype(str)
    df["text"] = df["text"].fillna("").astype(str)
    df["label"] = df["label"].fillna("").astype(str)
    df["event"] = df["event"].fillna("").astype(str)
    df["created_at"] = df["created_at"].apply(_parse_ts)
    df["source"] = args.source
    df["is_predicted"] = False

    client = bigquery.Client(project=args.project)
    table_id = f"{args.project}.{args.dataset}.{args.table}"

    job = client.load_table_from_dataframe(
        df[["tweet_id", "text", "label", "event", "created_at", "source", "is_predicted"]],
        table_id,
        job_config=bigquery.LoadJobConfig(write_disposition="WRITE_APPEND"),
    )
    job.result()
    print(f"Loaded {len(df)} rows into {table_id}")


if __name__ == "__main__":
    main()

