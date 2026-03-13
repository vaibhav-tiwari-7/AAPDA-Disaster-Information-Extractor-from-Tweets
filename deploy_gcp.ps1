Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "== GCP deploy: BigQuery + GCS + Cloud Function + Scheduler ==" -ForegroundColor Cyan

function Require-Cmd($name) {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
    throw "Missing command '$name'. Install Google Cloud CLI (gcloud/bq/gsutil) then re-run."
  }
}

Require-Cmd "gcloud"
Require-Cmd "bq"
Require-Cmd "gsutil"

if (-not $env:PROJECT_ID) { throw "Set env var PROJECT_ID" }
if (-not $env:REGION) { $env:REGION = "us-central1" }
if (-not $env:BUCKET) { throw "Set env var BUCKET (globally unique bucket name)" }
if (-not $env:BQ_DATASET) { $env:BQ_DATASET = "crisis_nlp" }

Push-Location $PSScriptRoot

Write-Host "Using PROJECT_ID=$($env:PROJECT_ID) REGION=$($env:REGION) BUCKET=$($env:BUCKET) BQ_DATASET=$($env:BQ_DATASET)" -ForegroundColor Gray

gcloud config set project $env:PROJECT_ID | Out-Null

Write-Host "Creating bucket (if not exists)..." -ForegroundColor Gray
gsutil ls -b "gs://$($env:BUCKET)" 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
  gsutil mb -p $env:PROJECT_ID -l $env:REGION "gs://$($env:BUCKET)"
}

Write-Host "Creating BigQuery dataset (if not exists)..." -ForegroundColor Gray
bq --location=$env:REGION mk -d --description "Crisis NLP dataset" "$($env:PROJECT_ID):$($env:BQ_DATASET)" 2>$null | Out-Null

Write-Host "Creating BigQuery tables..." -ForegroundColor Gray
bq query --use_legacy_sql=false --project_id=$env:PROJECT_ID < infra/bigquery/create_tables.sql

if (-not (Test-Path "artifacts/artifacts.joblib")) {
  throw "Missing artifacts/artifacts.joblib. Run .\\bootstrap_local.ps1 first."
}

Write-Host "Uploading model artifacts to GCS..." -ForegroundColor Gray
gsutil -m cp -r artifacts "gs://$($env:BUCKET)/models/latest"

Write-Host "Deploying Cloud Function batch_predict..." -ForegroundColor Gray
gcloud functions deploy batch_predict `
  --gen2 `
  --runtime=python312 `
  --region=$env:REGION `
  --source=cloud_function `
  --entry-point=main `
  --trigger-http `
  --allow-unauthenticated `
  --set-env-vars=PROJECT_ID=$env:PROJECT_ID,BQ_DATASET=$env:BQ_DATASET,MODEL_GCS_URI=gs://$env:BUCKET/models/latest/artifacts.joblib

$FUNCTION_URL = (gcloud functions describe batch_predict --region=$env:REGION --gen2 --format="value(serviceConfig.uri)")
Write-Host "Function URL: $FUNCTION_URL" -ForegroundColor Green

Write-Host "Creating/Updating Cloud Scheduler job (hourly)..." -ForegroundColor Gray
gcloud scheduler jobs describe crisis-batch-predict-hourly --location=$env:REGION 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
  gcloud scheduler jobs create http crisis-batch-predict-hourly `
    --schedule="0 * * * *" `
    --uri="$FUNCTION_URL" `
    --http-method=POST `
    --message-body="{}" `
    --time-zone="Etc/UTC" `
    --location=$env:REGION
} else {
  gcloud scheduler jobs update http crisis-batch-predict-hourly `
    --schedule="0 * * * *" `
    --uri="$FUNCTION_URL" `
    --http-method=POST `
    --message-body="{}" `
    --time-zone="Etc/UTC" `
    --location=$env:REGION
}

Write-Host ""
Write-Host "Done. Next:" -ForegroundColor Cyan
Write-Host "1) Load data to BigQuery: python scripts/load_raw_to_bq.py --project $env:PROJECT_ID --dataset $env:BQ_DATASET --csv data/humaid/train.csv" -ForegroundColor Yellow
Write-Host "2) Trigger function once: gcloud functions call batch_predict --region $env:REGION --gen2 --data '{}'" -ForegroundColor Yellow
Write-Host "3) Build Looker Studio dashboard from BigQuery tables predictions/alerts" -ForegroundColor Yellow

Pop-Location

