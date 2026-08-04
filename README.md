# Disaster Information Extractor from Tweets (Crisis Response) — GCP

End-to-end, low-cost crisis NLP pipeline on Google Cloud:

- **Storage**: Cloud Storage (datasets + trained model artifacts)
- **Warehouse**: BigQuery (`raw_tweets`, `predictions`, `alerts`, `audit_logs`)
- **ML**: baseline text classifier (TF‑IDF + Logistic Regression)
- **Automation**: Cloud Function `BatchPredict` + Cloud Scheduler trigger
- **Dashboard**: Looker Studio on BigQuery tables

This repo supports both:
- **HumAID**: uses tweet text directly (no rehydration needed).
- **CrisisNLP**: uses tweet IDs + labels; tweet text requires **rehydration** via X/Twitter API (optional).

---

## 1) Prereqs

- Python 3.10+ installed locally

- Google Cloud project with billing enabled (free-tier friendly)
- `gcloud` installed and authenticated
- Enable APIs:
  - BigQuery
  - Cloud Functions
  - Cloud Scheduler
  - Cloud Storage
  - (Optional) Secret Manager

---

## 2) Create resources (one-time)

Set variables (PowerShell):

```powershell
$env:PROJECT_ID="YOUR_PROJECT_ID"
$env:REGION="us-central1"
$env:BUCKET="YOUR_UNIQUE_BUCKET_NAME"
$env:BQ_DATASET="crisis_nlp"
```

Create a bucket:

```powershell
gsutil mb -p $env:PROJECT_ID -l $env:REGION gs://$env:BUCKET
```

Create BigQuery dataset:

```powershell
bq --location=$env:REGION mk -d `
  --description "Crisis NLP dataset" `
  $env:PROJECT_ID:$env:BQ_DATASET
```

Create tables:

```powershell
bq query --use_legacy_sql=false --project_id=$env:PROJECT_ID < infra/bigquery/create_tables.sql
```

---

## 3) Dataset format expected

Put your training data locally into:

- `data/humaid/train.csv` (recommended quick path)

CSV columns (minimum):
- `tweet_id` (string or int; can be empty for HumAID)
- `text` (string)
- `label` (string category)
- `event` (string)
- `created_at` (ISO timestamp string; optional)

Example labels (customize to your dataset):
- `infrastructure_damage`
- `request_help`
- `medical_emergency`
- `missing_person`
- `donation_request`
- `other`

---

## 4) Local train + evaluate

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

python scripts/train_model.py --train_csv data/humaid/train.csv --out_dir artifacts
python scripts/evaluate_model.py --model_dir artifacts --test_csv data/humaid/train.csv
```

Upload artifacts to GCS:

```powershell
gsutil -m cp -r artifacts gs://$env:BUCKET/models/latest
```

---

## 5) Load raw tweets to BigQuery

```powershell
python scripts/load_raw_to_bq.py --project $env:PROJECT_ID --dataset $env:BQ_DATASET --table raw_tweets --csv data/humaid/train.csv
```

---

## 6) Deploy Cloud Function (BatchPredict)

The Cloud Function:
- reads new/unpredicted rows from `raw_tweets`
- loads the latest model from GCS
- writes predictions to `predictions`
- writes high-priority items to `alerts`
- writes audit records to `audit_logs`

Deploy (Gen 2 HTTP):

```powershell
gcloud functions deploy batch_predict `
  --gen2 `
  --runtime=python312 `
  --region=$env:REGION `
  --source=cloud_function `
  --entry-point=main `
  --trigger-http `
  --allow-unauthenticated `
  --set-env-vars=PROJECT_ID=$env:PROJECT_ID,BQ_DATASET=$env:BQ_DATASET,MODEL_GCS_URI=gs://$env:BUCKET/models/latest/artifacts.joblib
```

Test call:

```powershell
gcloud functions call batch_predict --region=$env:REGION --gen2 --data '{}'
```

---

## 7) Schedule it

Create a scheduler job (hourly):

```powershell
$FUNCTION_URL=(gcloud functions describe batch_predict --region=$env:REGION --gen2 --format="value(serviceConfig.uri)")

gcloud scheduler jobs create http crisis-batch-predict-hourly `
  --schedule="0 * * * *" `
  --uri="$FUNCTION_URL" `
  --http-method=POST `
  --message-body="{}" `
  --time-zone="Etc/UTC" `
  --location=$env:REGION
```

---

## 8) Looker Studio dashboard

In Looker Studio:
- Add BigQuery data source:
  - `crisis_nlp.predictions` (category distribution, trends)
  - `crisis_nlp.alerts` (priority queue list)
- Build:
  - event-wise counts by `predicted_label`
  - time series by `predicted_at` (hour/day)
  - table of latest `alerts` with filters

---

## 9) About API keys (tweet rehydration + Gemini)

### X/Twitter API key (tweet rehydration)
If you use CrisisNLP tweet IDs and need the tweet text, you typically use:
- **X API Bearer Token** (recommended) for `GET /2/tweets?ids=...`
- Or OAuth 1.0a user context (more complex)

You create it in the X Developer Portal and store it as:
- env var `X_BEARER_TOKEN` (locally) or Secret Manager (in cloud)

Important: rehydration is subject to X API access level and tweet availability (deleted/protected tweets won’t return).

### Gemini / “NLP key”
For the baseline classifier in this project (**TF‑IDF + Logistic Regression**), you **do not need Gemini** or any LLM key.

If you later want LLM-based classification/summarization, you’d use:
- **Google AI Studio** API key (Gemini API) *or*
- **Vertex AI** (recommended on GCP) using service account auth (no “API key” needed in code, uses IAM).

This repo starts with the ML baseline because it’s cheap, fast, auditable, and easy to evaluate.

---

## Repo layout

- `infra/bigquery/create_tables.sql` — BigQuery DDL
- `scripts/` — local training/eval/load utilities
- `crisis_nlp/` — shared preprocessing + model utils
- `cloud_function/` — deployable `batch_predict` function

#