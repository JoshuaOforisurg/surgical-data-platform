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

By default, the local synthetic path is regenerated with 1000 clinically aligned
preference cards before the pipeline runs. Override the scale with:

```bash
SYNTHETIC_RECORD_COUNT=250 python main_orchestrator.py
```

Generate one structured source file per card for ingestion scale testing:

```bash
python main_orchestrator.py \
  --synthetic-count 1000 \
  --synthetic-output-mode partitioned \
  --synthetic-file-formats json,csv
```

Use the existing synthetic file without regeneration:

```bash
python main_orchestrator.py --use-existing-synthetic
```

Generate synthetic cards directly:

```bash
python -m generate_synthetic_data.main_synthetic_generator --count 1000
python -m generate_synthetic_data.main_synthetic_generator \
  --count 1000 \
  --output-mode partitioned \
  --file-formats json,csv
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
s3://surgical-data/gold/operational/drafts/{timestamp}_{draft_id}.json
```

## Postgres Schemas

```text
bronze_raw.ingested_files
bronze_raw.ingested_records
pipeline_audit.pipeline_runs
metadata_catalog.object_store_objects
metadata_catalog.gold_artifacts
iceberg_catalog.catalog_bootstrap
```

Useful inspection queries:

```sql
select status, records_processed, gold_operational_key
from pipeline_audit.pipeline_runs
order by started_at desc
limit 5;

select layer, artifact_type, count(*)
from metadata_catalog.object_store_objects
group by layer, artifact_type
order by layer, artifact_type;

select *
from iceberg_catalog.catalog_bootstrap;
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

Synthetic catalogue data is modularized under:

```text
generate_synthetic_data/catalogue/
```

`generate_synthetic_data/mock_data.py` remains as a compatibility facade for
older imports while new procedure, supply, surgeon, and instruction data lives
in smaller catalogue modules.

## Frontline Drafts

Streamlit reads the current operational Gold file from MinIO and allows staff
to save draft edits or new draft preference cards. Drafts are written to MinIO
under `gold/operational/drafts/` with `pending_review` status. They are not
silently promoted over the operational Gold card.
