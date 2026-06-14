# Surgeon Preference Card Pipeline

Production-oriented local pipeline for messy surgeon preference data.

## Current Architecture

```text
Synthetic or uploaded source files
        |
        v
MinIO landing/
        |
        v
Postgres bronze ledger
        |
        v
Optional Iceberg SQL catalog bootstrap
        |
        v
Silver A structural cleanup
        |
        v
Silver B clinical enrichment and validation
        |
        v
Gold operational preference cards + Gold analytics snapshot
        |
        v
MinIO gold/
        |
        v
Streamlit reads gold/operational/latest/gold_operational_preference_cards.csv
```

## Main Entry Points

Run the full pipeline:

```bash
python main_orchestrator.py --source generate_synthetic_data/output/master_preferences.json
```

Run the Streamlit UI:

```bash
streamlit run app.py
```

Run the local stack:

```bash
docker compose up --build
```

## Storage Layout

```text
s3://surgical-data/landing/{run_id}/...
s3://surgical-data/bronze/manifests/{run_id}.json
s3://surgical-data/gold/operational/runs/{run_id}/gold_operational_preference_cards.csv
s3://surgical-data/gold/operational/latest/gold_operational_preference_cards.csv
s3://surgical-data/gold/analytics/runs/{run_id}/gold_analytics_report.json
s3://surgical-data/gold/analytics/latest/gold_analytics_report.json
```

## Postgres Schemas

```text
bronze_raw.ingested_files
bronze_raw.ingested_records
pipeline_audit.pipeline_runs
```

When `pyiceberg` is installed, the pipeline also attempts to bootstrap an
Iceberg SQL catalog namespace using the same Postgres service and the MinIO
warehouse path.
