from __future__ import annotations

import dataclasses
import hashlib
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from crisis_nlp.preprocess import normalize_text


@dataclasses.dataclass(frozen=True)
class ModelArtifact:
    model: Pipeline
    labels: List[str]
    model_version: str
    created_at: str
    metadata: Dict[str, object]


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_hash(obj: object) -> str:
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def build_pipeline(max_features: int = 50000) -> Pipeline:
    vectorizer = TfidfVectorizer(
        preprocessor=normalize_text,
        token_pattern=r"(?u)\b\w+\b",
        ngram_range=(1, 2),
        max_features=max_features,
        min_df=2,
    )
    clf = LogisticRegression(
        max_iter=2000,
        n_jobs=None,
        class_weight="balanced",
    )
    return Pipeline([("tfidf", vectorizer), ("clf", clf)])


def train_model(
    texts: List[str],
    labels: List[str],
    *,
    max_features: int = 50000,
    extra_metadata: Optional[Dict[str, object]] = None,
) -> ModelArtifact:
    pipeline = build_pipeline(max_features=max_features)
    pipeline.fit(texts, labels)

    label_set = sorted({str(x) for x in labels})
    meta = {
        "max_features": max_features,
        "label_set": label_set,
        "trained_on": len(texts),
        "created_at": _utc_iso(),
    }
    if extra_metadata:
        meta.update(extra_metadata)

    model_version = _stable_hash(meta)

    return ModelArtifact(
        model=pipeline,
        labels=label_set,
        model_version=model_version,
        created_at=meta["created_at"],
        metadata=meta,
    )


def predict(
    artifact: ModelArtifact,
    texts: List[str],
) -> Tuple[List[str], List[float]]:
    model = artifact.model
    preds = model.predict(texts).tolist()

    proba: List[float] = []
    if hasattr(model, "predict_proba"):
        p = model.predict_proba(texts)
        proba = np.max(p, axis=1).astype(float).tolist()
    else:
        proba = [float("nan")] * len(preds)
    return preds, proba


def save_artifact(artifact: ModelArtifact, path: str) -> None:
    payload = {
        "model": artifact.model,
        "labels": artifact.labels,
        "model_version": artifact.model_version,
        "created_at": artifact.created_at,
        "metadata": artifact.metadata,
    }
    joblib.dump(payload, path)


def load_artifact(path: str) -> ModelArtifact:
    payload = joblib.load(path)
    return ModelArtifact(
        model=payload["model"],
        labels=list(payload.get("labels", [])),
        model_version=str(payload["model_version"]),
        created_at=str(payload.get("created_at", "")),
        metadata=dict(payload.get("metadata", {})),
    )

