from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from google.cloud import bigquery
from google.cloud import storage

from crisis_nlp.io import new_id, utc_now
from crisis_nlp.modeling import load_artifact, predict
from crisis_nlp.rule_engine import decide_alert


PROJECT_ID = os.environ.get("PROJECT_ID", "")
BQ_DATASET = os.environ.get("BQ_DATASET", "crisis_nlp")
MODEL_GCS_URI = os.environ.get("MODEL_GCS_URI", "")

RAW_TABLE = f"{PROJECT_ID}.{BQ_DATASET}.raw_tweets"
PRED_TABLE = f"{PROJECT_ID}.{BQ_DATASET}.predictions"
ALERTS_TABLE = f"{PROJECT_ID}.{BQ_DATASET}.alerts"
AUDIT_TABLE = f"{PROJECT_ID}.{BQ_DATASET}.audit_logs"


def _parse_gcs_uri(uri: str) -> Tuple[str, str]:
    if not uri.startswith("gs://"):
        raise ValueError("MODEL_GCS_URI must start with gs://")
    no = uri[len("gs://") :]
    bucket, _, blob = no.partition("/")
    if not bucket or not blob:
        raise ValueError("MODEL_GCS_URI must be like gs://bucket/path/to/file")
    return bucket, blob


def _download_model(local_path: str) -> None:
    bucket_name, blob_name = _parse_gcs_uri(MODEL_GCS_URI)
    st = storage.Client(project=PROJECT_ID)
    b = st.bucket(bucket_name)
    blob = b.blob(blob_name)
    blob.download_to_filename(local_path)


def _bq() -> bigquery.Client:
    return bigquery.Client(project=PROJECT_ID)


def _insert_rows(table: str, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    client = _bq()
    errors = client.insert_rows_json(table, rows)
    if errors:
        raise RuntimeError(f"BigQuery insert errors for {table}: {errors}")


def _mark_predicted(tweet_ids: List[str]) -> None:
    if not tweet_ids:
        return
    client = _bq()
    job = client.query(
        f"""
        UPDATE `{RAW_TABLE}`
        SET is_predicted = TRUE
        WHERE tweet_id IN UNNEST(@ids)
        """,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ArrayQueryParameter("ids", "STRING", tweet_ids)]
        ),
    )
    job.result()


def _fetch_batch(limit: int = 500) -> List[Dict[str, Any]]:
    client = _bq()
    # Prefer unpredicted rows; keep idempotency by only selecting those.
    q = f"""
    SELECT tweet_id, text, label, event, created_at
    FROM `{RAW_TABLE}`
    WHERE is_predicted = FALSE
      AND text IS NOT NULL
      AND LENGTH(TRIM(text)) > 0
    ORDER BY ingested_at ASC
    LIMIT @limit
    """
    job = client.query(
        q,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("limit", "INT64", limit)]
        ),
    )
    return [dict(r) for r in job.result()]


def main(request):  # Cloud Functions HTTP entrypoint
    started = utc_now()
    audit_id = new_id("audit")

    if not PROJECT_ID or not MODEL_GCS_URI:
        return (
            json.dumps({"error": "Missing PROJECT_ID or MODEL_GCS_URI env var"}),
            500,
            {"Content-Type": "application/json"},
        )

    try:
        payload = request.get_json(silent=True) or {}
        limit = int(payload.get("limit", 500))

        rows = _fetch_batch(limit=limit)
        texts = [r.get("text", "") for r in rows]
        tweet_ids = [str(r.get("tweet_id") or "") for r in rows]

        model_path = None
        with tempfile.TemporaryDirectory() as td:
            model_path = os.path.join(td, "artifacts.joblib")
            _download_model(model_path)
            artifact = load_artifact(model_path)

            y_pred, y_proba = predict(artifact, texts)

        now = datetime.now(timezone.utc).isoformat()
        pred_rows: List[Dict[str, Any]] = []
        alert_rows: List[Dict[str, Any]] = []

        for r, plabel, pprob in zip(rows, y_pred, y_proba):
            prediction_id = new_id("pred")
            pred_rows.append(
                {
                    "prediction_id": prediction_id,
                    "tweet_id": r.get("tweet_id"),
                    "event": r.get("event"),
                    "text": r.get("text"),
                    "true_label": r.get("label"),
                    "predicted_label": plabel,
                    "predicted_proba": float(pprob) if pprob == pprob else None,  # NaN-safe
                    "model_version": artifact.model_version,
                    "model_gcs_uri": MODEL_GCS_URI,
                    "predicted_at": now,
                }
            )

            decision = decide_alert(plabel, float(pprob) if pprob == pprob else None)
            if decision.should_alert:
                alert_rows.append(
                    {
                        "alert_id": new_id("alert"),
                        "prediction_id": prediction_id,
                        "tweet_id": r.get("tweet_id"),
                        "event": r.get("event"),
                        "text": r.get("text"),
                        "predicted_label": plabel,
                        "priority": decision.priority or "high",
                        "reason": decision.reason,
                        "model_version": artifact.model_version,
                        "created_at": now,
                        "status": "open",
                    }
                )

        _insert_rows(PRED_TABLE, pred_rows)
        _insert_rows(ALERTS_TABLE, alert_rows)
        _mark_predicted(tweet_ids)

        finished = utc_now()
        _insert_rows(
            AUDIT_TABLE,
            [
                {
                    "audit_id": audit_id,
                    "action": "batch_predict",
                    "model_version": artifact.model_version,
                    "model_gcs_uri": MODEL_GCS_URI,
                    "rows_read": len(rows),
                    "rows_predicted": len(pred_rows),
                    "rows_alerted": len(alert_rows),
                    "started_at": started.isoformat(),
                    "finished_at": finished.isoformat(),
                    "status": "success",
                    "details": f"limit={limit}",
                }
            ],
        )

        return (
            json.dumps(
                {
                    "status": "ok",
                    "rows_read": len(rows),
                    "rows_predicted": len(pred_rows),
                    "rows_alerted": len(alert_rows),
                    "model_version": artifact.model_version,
                }
            ),
            200,
            {"Content-Type": "application/json"},
        )
    except Exception as e:
        finished = utc_now()
        try:
            _insert_rows(
                AUDIT_TABLE,
                [
                    {
                        "audit_id": audit_id,
                        "action": "batch_predict",
                        "model_version": None,
                        "model_gcs_uri": MODEL_GCS_URI,
                        "rows_read": None,
                        "rows_predicted": None,
                        "rows_alerted": None,
                        "started_at": started.isoformat(),
                        "finished_at": finished.isoformat(),
                        "status": "error",
                        "details": str(e)[:2000],
                    }
                ],
            )
        except Exception:
            pass
        return (
            json.dumps({"status": "error", "message": str(e)}),
            500,
            {"Content-Type": "application/json"},
        )

