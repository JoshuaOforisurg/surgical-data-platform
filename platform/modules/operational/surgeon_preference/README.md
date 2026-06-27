# Surgeon Preference Card Pipeline

Production-oriented local pipeline for messy surgeon preference data.

## Current Architecture

```text
Synthetic or uploaded source files
        |
        v
Object storage landing/
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
Object storage gold/
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

Create local secrets from the example template before running the stack:

```bash
cp .env.example .env
```

Fill `DB_PASSWORD` and `MINIO_ROOT_PASSWORD` in your local `.env` before
starting Docker. Keep `.env` local only. It is ignored by Git and excluded from
Docker build contexts so credentials are supplied at runtime instead of being
committed or baked into images.

When inspecting the Docker Postgres database from a local GUI such as pgAdmin
or DBeaver, connect to host `127.0.0.1` on port `5433` by default. The
container still uses port `5432` internally, but the host port is shifted to
avoid clashing with a native Postgres install on the laptop.

## Storage Layout

The same logical prefixes are used in local MinIO and Azure Blob Storage.
Locally, URIs are recorded as `s3://...`. When
`AZURE_STORAGE_CONNECTION_STRING` is set, the pipeline writes to Azure Blob and
records URIs as `azblob://...`.

```text
landing/{run_id}/...
bronze/manifests/{run_id}.json
gold/operational/runs/{run_id}/gold_operational_preference_cards.csv
gold/operational/latest/gold_operational_preference_cards.csv
gold/analytics/runs/{run_id}/gold_analytics_report.json
gold/analytics/latest/gold_analytics_report.json
gold/operational/drafts/{timestamp}_{draft_id}.json
```

To run the pipeline against Azure Blob from your laptop, set the Azure storage
environment variables before running the normal pipeline command:

```bash
export AZURE_STORAGE_CONNECTION_STRING="<your Azure storage connection string>"
export AZURE_CONTAINER_NAME="surgeon-preference"
python main_orchestrator.py --source examples --use-existing-synthetic
```

After the run, the Azure container should contain objects under `landing/`,
`bronze/`, `gold/operational/latest/`, and `gold/analytics/latest/`.

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
the warehouse at the active object store:

```text
s3://surgeon-preference/iceberg-warehouse
azblob://surgeon-preference/iceberg-warehouse
```

This creates the catalogue metadata foundation needed for a future Azure-ready
lakehouse. The current production path still writes Bronze metadata to
Postgres and publishes operational/analytics Gold files to object storage.
Writing Silver and Gold as Iceberg tables is the next storage-hardening step.

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

Streamlit reads the current operational Gold file from object storage and
allows staff to save draft edits or new draft preference cards. Drafts are
written under `gold/operational/drafts/` with `pending_review` status. They are
not silently promoted over the operational Gold card.

## Azure And FHIR Learning Plan

Before migrating this module to Azure, follow the guided plan in
`docs/azure_migration_learning_plan.md`. It separates the current standalone
medallion pipeline from the future EHR-integrated pipeline and explains where a
FHIR adapter fits without replacing the internal surgeon preference-card domain
model.

The intended migration path has two phases:

1. Standalone Azure pipeline for uploaded/synthetic preference-card data.
2. EHR-integrated pipeline where FHIR messages are adapted into the same
   internal preference-card event model.

FHIR should be treated as the EHR integration boundary. It provides standard
clinical context such as `ServiceRequest`, `Appointment`, `Encounter`,
`Practitioner`, and `Procedure`; the theatre-specific preference-card model
remains internal to this module.
