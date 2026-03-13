from __future__ import annotations

import argparse

import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix

from crisis_nlp.modeling import load_artifact, predict


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--model_dir", required=True, help="Directory containing artifacts.joblib")
    p.add_argument("--test_csv", required=True)
    args = p.parse_args()

    artifact = load_artifact(f"{args.model_dir.rstrip('/').rstrip('\\\\')}\\artifacts.joblib")
    df = pd.read_csv(args.test_csv)

    texts = df["text"].fillna("").astype(str).tolist()
    y_true = df["label"].fillna("other").astype(str).tolist()

    y_pred, _ = predict(artifact, texts)

    print(f"Model version: {artifact.model_version}")
    print("\nClassification report:")
    print(classification_report(y_true, y_pred, digits=3, zero_division=0))
    print("\nConfusion matrix (labels sorted):")
    labels_sorted = sorted(set(y_true) | set(y_pred))
    cm = confusion_matrix(y_true, y_pred, labels=labels_sorted)
    print("labels:", labels_sorted)
    print(cm)


if __name__ == "__main__":
    main()

