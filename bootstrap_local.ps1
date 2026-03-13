Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "== Local bootstrap: venv + deps + train + eval ==" -ForegroundColor Cyan

Push-Location $PSScriptRoot

if (-not (Test-Path ".venv")) {
  python -m venv .venv
}

& ".\.venv\Scripts\Activate.ps1"
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .

if (-not (Test-Path "data/humaid/train.csv")) {
  throw "Missing data/humaid/train.csv. Add your dataset (or keep the starter file)."
}

python scripts/train_model.py --train_csv data/humaid/train.csv --out_dir artifacts
python scripts/evaluate_model.py --model_dir artifacts --test_csv data/humaid/train.csv

Write-Host ""
Write-Host "Local artifacts saved to: artifacts\artifacts.joblib" -ForegroundColor Green
Write-Host "Next: install Google Cloud CLI to deploy to GCP." -ForegroundColor Yellow

Pop-Location

