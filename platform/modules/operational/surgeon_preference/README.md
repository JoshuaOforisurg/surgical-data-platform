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
Postgres-backed Iceberg SQL catalog bootstrap
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

## Iceberg Status

The pipeline now bootstraps a Postgres-backed Iceberg SQL catalog and points
the warehouse at MinIO:

```text
s3://surgical-data/iceberg-warehouse
```

This creates the catalogue metadata foundation needed for a future Azure-ready
lakehouse. The current production path still writes Bronze metadata to
Postgres and publishes operational/analytics Gold files to MinIO. Writing
Silver and Gold as Iceberg tables is the next storage-hardening step.

## Clinical Reference Scaling

The clinical catalogue is now exposed through `domain.clinical_reference_service`.
That service presents the reference data as normalized tables:

```text
procedure_table()
instrument_system_table()
supply_profile_table()
```

Silver-B should use this service contract rather than reaching directly into
raw dictionaries as the dataset grows. The current backing store is local
Python reference data; the same service shape can later be backed by Postgres,
Iceberg tables, or an API without changing the enrichment pipeline.

The catalogue also canonicalises frontline-facing special instructions so messy
source text such as spacing errors or typos is cleaned before it reaches the
operational Gold card.
