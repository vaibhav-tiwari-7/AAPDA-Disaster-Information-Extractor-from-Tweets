from __future__ import annotations

import argparse
import os
from pathlib import Path

import pandas as pd

from crisis_nlp.modeling import save_artifact, train_model


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--train_csv", required=True)
    p.add_argument("--out_dir", required=True)
    p.add_argument("--max_features", type=int, default=50000)
    args = p.parse_args()

    df = pd.read_csv(args.train_csv)
    if "text" not in df.columns or "label" not in df.columns:
        raise SystemExit("CSV must contain columns: text,label (and optional tweet_id,event,created_at)")

    texts = df["text"].fillna("").astype(str).tolist()
    labels = df["label"].fillna("other").astype(str).tolist()

    extra = {
        "train_csv": os.path.basename(args.train_csv),
        "rows": int(len(df)),
        "unique_labels": int(df["label"].nunique(dropna=True)),
    }
    artifact = train_model(texts, labels, max_features=args.max_features, extra_metadata=extra)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "artifacts.joblib"
    save_artifact(artifact, str(out_path))

    meta_path = out_dir / "metadata.txt"
    meta_path.write_text(
        f"model_version={artifact.model_version}\ncreated_at={artifact.created_at}\nmetadata={artifact.metadata}\n",
        encoding="utf-8",
    )

    print(f"Saved model to: {out_path}")
    print(f"Model version: {artifact.model_version}")


if __name__ == "__main__":
    main()

