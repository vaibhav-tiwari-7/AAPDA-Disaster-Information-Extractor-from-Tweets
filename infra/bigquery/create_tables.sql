-- Dataset must already exist: ${PROJECT_ID}:${BQ_DATASET}
-- Run:
--   bq query --use_legacy_sql=false --project_id=$PROJECT_ID < infra/bigquery/create_tables.sql

DECLARE project_id STRING DEFAULT @@project_id;
DECLARE dataset_id STRING DEFAULT 'crisis_nlp';

EXECUTE IMMEDIATE FORMAT("""
CREATE TABLE IF NOT EXISTS `%s.%s.raw_tweets` (
  tweet_id STRING,
  text STRING,
  label STRING,
  event STRING,
  created_at TIMESTAMP,
  ingested_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP(),
  source STRING,
  is_predicted BOOL NOT NULL DEFAULT FALSE
)
""", project_id, dataset_id);

EXECUTE IMMEDIATE FORMAT("""
CREATE TABLE IF NOT EXISTS `%s.%s.predictions` (
  prediction_id STRING NOT NULL,
  tweet_id STRING,
  event STRING,
  text STRING,
  true_label STRING,
  predicted_label STRING NOT NULL,
  predicted_proba FLOAT64,
  model_version STRING NOT NULL,
  model_gcs_uri STRING NOT NULL,
  predicted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP()
)
PARTITION BY DATE(predicted_at)
""", project_id, dataset_id);

EXECUTE IMMEDIATE FORMAT("""
CREATE TABLE IF NOT EXISTS `%s.%s.alerts` (
  alert_id STRING NOT NULL,
  prediction_id STRING NOT NULL,
  tweet_id STRING,
  event STRING,
  text STRING,
  predicted_label STRING NOT NULL,
  priority STRING NOT NULL,
  reason STRING,
  model_version STRING NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP(),
  status STRING NOT NULL DEFAULT 'open'
)
PARTITION BY DATE(created_at)
""", project_id, dataset_id);

EXECUTE IMMEDIATE FORMAT("""
CREATE TABLE IF NOT EXISTS `%s.%s.audit_logs` (
  audit_id STRING NOT NULL,
  action STRING NOT NULL,
  model_version STRING,
  model_gcs_uri STRING,
  rows_read INT64,
  rows_predicted INT64,
  rows_alerted INT64,
  started_at TIMESTAMP NOT NULL,
  finished_at TIMESTAMP,
  status STRING NOT NULL,
  details STRING
)
PARTITION BY DATE(started_at)
""", project_id, dataset_id);

