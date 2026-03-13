from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import List

import altair as alt
import pandas as pd
import streamlit as st

from crisis_nlp.modeling import load_artifact, predict
from crisis_nlp.rule_engine import decide_alert


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


st.set_page_config(page_title="Crisis Tweet Classifier (Local)", layout="wide")
st.title("Crisis Tweet Classifier (Local)")

model_path = st.sidebar.text_input("Model path", value="artifacts/artifacts.joblib")
artifact = None
try:
    artifact = load_artifact(model_path)
    st.sidebar.success(f"Loaded model version: {artifact.model_version}")
except Exception as e:
    st.sidebar.error(f"Failed to load model: {e}")

st.sidebar.markdown("### Live X/Twitter (optional)")
st.sidebar.caption("Set `X_BEARER_TOKEN` env var to enable live fetch.")


def _add_predictions(df: pd.DataFrame) -> pd.DataFrame:
    if artifact is None:
        raise RuntimeError("Model not loaded.")
    texts: List[str] = df["text"].fillna("").astype(str).tolist()
    y_pred, y_proba = predict(artifact, texts)
    out = df.copy()
    out["predicted_label"] = y_pred
    out["predicted_proba"] = y_proba

    alerted = []
    priorities = []
    reasons = []
    for lab, pr in zip(y_pred, y_proba):
        d = decide_alert(lab, float(pr) if pr == pr else None)
        alerted.append(bool(d.should_alert))
        priorities.append(d.priority)
        reasons.append(d.reason)
    out["is_alert"] = alerted
    out["priority"] = priorities
    out["reason"] = reasons
    return out


def _ensure_datetime(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce", utc=True)


def _trend_chart(df: pd.DataFrame, *, time_col: str, group_col: str, title: str) -> alt.Chart:
    d = df.copy()
    d[time_col] = _ensure_datetime(d[time_col])
    d = d.dropna(subset=[time_col])
    if d.empty:
        return alt.Chart(pd.DataFrame({"note": ["No timestamps available for trend chart"]})).mark_text(
            size=14
        ).encode(text="note")

    d["date_hour"] = d[time_col].dt.floor("h")
    agg = d.groupby(["date_hour", group_col], as_index=False).size().rename(columns={"size": "count"})
    chart = (
        alt.Chart(agg, title=title)
        .mark_line(point=True)
        .encode(
            x=alt.X("date_hour:T", title="Time (hour)"),
            y=alt.Y("count:Q", title="Tweets"),
            color=alt.Color(f"{group_col}:N", title=group_col),
            tooltip=["date_hour:T", group_col, "count:Q"],
        )
        .properties(height=320)
    )
    return chart


def _category_compare_chart(df: pd.DataFrame, *, category_col: str, series_col: str, title: str) -> alt.Chart:
    agg = df.groupby([series_col, category_col], as_index=False).size().rename(columns={"size": "count"})
    chart = (
        alt.Chart(agg, title=title)
        .mark_bar()
        .encode(
            x=alt.X("count:Q", title="Count"),
            y=alt.Y(f"{category_col}:N", sort="-x", title="Category"),
            color=alt.Color(f"{series_col}:N", title=series_col),
            tooltip=[series_col, category_col, "count:Q"],
        )
        .properties(height=360)
    )
    return chart


tab1, tab2 = st.tabs(["Single tweet", "Batch (CSV)"])

with tab1:
    st.subheader("Classify one tweet")
    text = st.text_area("Tweet text", height=120, placeholder="Paste a disaster-related tweet here…")
    if st.button("Predict", type="primary", disabled=artifact is None or not text.strip()):
        y_pred, y_proba = predict(artifact, [text])
        label = y_pred[0]
        proba = y_proba[0]
        st.write({"predicted_label": label, "predicted_proba": proba, "predicted_at": _utc_iso()})
        decision = decide_alert(label, proba if proba == proba else None)
        if decision.should_alert:
            st.warning(f"ALERT: priority={decision.priority} reason={decision.reason}")
        else:
            st.info("No alert triggered by rule engine.")

with tab2:
    st.subheader("Classify a CSV batch")
    st.caption("CSV must contain at least a `text` column. Optional: tweet_id,event,label")
    uploaded = st.file_uploader("Upload CSV", type=["csv"])
    example_path = Path("data/humaid/train.csv")
    if example_path.exists():
        st.caption(f"Example file available at `{example_path.as_posix()}`")

    if uploaded is not None and artifact is not None:
        df = pd.read_csv(uploaded)
        if "text" not in df.columns:
            st.error("CSV is missing required column: text")
        else:
            out = _add_predictions(df)
            out["predicted_at"] = _utc_iso()

            # Define alerts purely as the highest-confidence predictions in this batch.
            alerts = out.copy()
            alerts = alerts[pd.notna(alerts["predicted_proba"])]
            alerts = alerts.sort_values("predicted_proba", ascending=False)

            c1, c2 = st.columns([2, 1])
            with c1:
                st.dataframe(out, use_container_width=True)

                if not alerts.empty:
                    st.markdown("### Top 5 highest-confidence tweets")
                    st.dataframe(
                        alerts[
                            [
                                "predicted_label",
                                "predicted_proba",
                                "event",
                                "text",
                            ]
                        ].head(5),
                        use_container_width=True,
                    )
                else:
                    st.info("No alerts detected in this batch.")

            with c2:
                st.subheader("Counts")
                st.bar_chart(out["predicted_label"].value_counts())
                st.subheader("Top 25 by confidence")
                st.write(alerts[["predicted_label", "predicted_proba", "event"]].head(25))

            st.download_button(
                "Download results CSV",
                data=out.to_csv(index=False).encode("utf-8"),
                file_name="predictions_local.csv",
                mime="text/csv",
            )
