# Stock & Inventory Management Pipeline

Production-minded operational data product for surgical theatre stock readiness,
shortage detection, substitutions, reorder planning, and usage/cost analysis.

This module is intentionally shaped as a sibling of the completed
`surgeon_preference` pipeline v1. The first implementation step is a clinically
aligned synthetic data generator that uses the existing surgeon preference
procedure profiles as its source of expected theatre demand.

## Planned Architecture

```text
Synthetic, spreadsheet, scanner, ERP, vendor, and theatre usage sources
        |
        v
Object storage landing/
        |
        v
Bronze raw file and record ledger
        |
        v
Silver A structural normalisation
        |
        v
Silver B item catalogue, lot, location, substitution, and safety enrichment
        |
        v
Gold operational readiness, shortages, reorder planning, and analytics
```

## Current Step

Generate source-like stock data:

Outputs are written to `synthetic_data/generated/` by default and include:

```text
item_catalogue.csv/json
stock_lots.csv/json
erp_stock_balances.csv/json
manual_stocktake_spreadsheet.csv/json
scanner_stock_events.jsonl/csv
stock_movements.csv/json
upcoming_case_demand.csv/json
supplier_catalogue.csv/json
substitution_rules.csv/json
generation_manifest.json
```

Generate a fresh source bundle:

```bash
python3 -m generate_synthetic_data.main_synthetic_stock_generator \
  --output-dir synthetic_data/generated \
  --event-count 250 \
  --movement-count 250 \
  --case-count 25 \
  --seed 42
```

The generator uses a fixed default `--run-date` for reproducibility. Pass a
different ISO-8601 run date when you want a new anchored synthetic day. Use
`--print-manifest` to print the full manifest JSON; otherwise the CLI prints a
short summary and writes the data files to disk.

CSV outputs are intentionally messy by default: spreadsheet-style headers,
human boolean values, comma-formatted numbers, GBP currency strings, and
UK-style dates are introduced so the ETL pipeline has realistic cleanup work.
JSON and JSONL outputs remain clean reference sources. Pass `--clean-sources`
when you want clean CSV files too.

## Bronze Ingestion

Land generated or source-like files into the local bronze layer:

```bash
python3 bronze_ingestion/loader/bronze_pipeline.py \
  --source synthetic_data/generated
```

The bronze run copies original files to `data_lake/bronze/raw/<run_id>/`,
writes auditable wrapped records to `data_lake/bronze/records/<run_id>/`, and
publishes a run manifest to `data_lake/bronze/manifests/<run_id>.json`.

Bronze runs are append-only: an existing `run_id` is never overwritten. When a
directory contains multiple representations of the same dataset, such as CSV and
JSON, all raw files are landed but one source is marked `canonical_for_silver`
using the default priority `jsonl,json,csv`. Override that with:

```bash
python3 bronze_ingestion/loader/bronze_pipeline.py \
  --source synthetic_data/generated \
  --canonical-format-priority jsonl,json,csv
```

To exercise the messy spreadsheet cleanup path, prefer CSV sources:

```bash
python3 -m orchestration.run_pipeline \
  --source-dir synthetic_data/generated \
  --canonical-format-priority csv,jsonl,json
```

## Silver A Normalisation

Transform canonical bronze records into structurally normalised Silver A tables:

```bash
python3 silver_transform/silver_a/transformer.py \
  --bronze-manifest data_lake/bronze/manifests/<run_id>.json
```

If no manifest is supplied, the latest bronze manifest is used. Silver A writes
one JSONL table per canonical dataset to `data_lake/silver_a/records/<run_id>/`
and a transform manifest to `data_lake/silver_a/manifests/<run_id>.json`.
Rows are not dropped during structural validation; validation issues are written
to each Silver A record in `validation_errors`.

## Silver B Enrichment

Join Silver A tables into operational stock facts:

```bash
python3 silver_transform/silver_b/transformer.py \
  --silver-a-manifest data_lake/silver_a/manifests/<run_id>.json
```

Silver B currently writes:

```text
stock_positions.jsonl
case_readiness.jsonl
usage_analytics.jsonl
```

Stock positions enrich lots with catalogue, location, ERP balance, expiry,
recall, sterility, reorder, and value fields. Case readiness compares upcoming
case demand with usable stock and flags ready, shortage, or substitution
available states. Quarantined, expired, awaiting-sterilisation, and unavailable
stock is excluded. Cases are processed in scheduled order and primary stock is
allocated once, so later cases cannot reuse quantity already assigned to an
earlier case. Usage analytics summarise item movement, issue, waste, return, and
estimated issue cost signals from stock movements.

## Gold Outputs

Publish operational outputs for review and dashboards:

```bash
python3 gold_cleaned/publisher.py \
  --silver-b-manifest data_lake/silver_b/manifests/<run_id>.json
```

Gold currently writes:

```text
case_readiness_summary.json/csv
shortage_worklist.json
reorder_worklist.json
usage_cost_summary.json
inventory_risk_summary.json
surgeon_readiness_summary.json
procedure_readiness_summary.json
```

The surgeon and procedure summaries aggregate case readiness, shortages,
critical shortages, catalogue mapping gaps, and readiness rates. Every case
summary retains the source preference card UID and version for traceability.

## Surgeon Preference Handoff

The stock generator can consume the surgeon preference pipeline's operational
Gold JSON instead of inventing preference-card demand from shared profiles:

```bash
python3 -m orchestration.run_pipeline \
  --source-dir synthetic_data/generated \
  --surgeon-preference-gold \
    ../surgeon_preference/data_lake/gold/gold_operational_preference_cards.json
```

This path loads current, non-quarantined preference cards, expands their item
JSON fields into case demand lines, and resolves item names against the stock
catalogue. An item that cannot be resolved is assigned an auditable
`UNMAPPED-*` ID and remains visible as unavailable demand. It is never silently
dropped or counted as ready.

The recommended local cross-pipeline run order is:

1. Run the surgeon preference pipeline to refresh operational Gold.
2. Run the stock pipeline with `--surgeon-preference-gold`.
3. Run the stock quality gates.
4. Publish the accepted run to MinIO and open Streamlit.

## Dashboard Service

Dashboard-facing code can load Gold outputs without knowing the file layout:

```python
from streamlit_services import dashboard_snapshot

snapshot = dashboard_snapshot("data_lake/gold/manifests/<run_id>.json")
```

The snapshot exposes headline counts, readiness and availability distributions,
top shortages, surgeon and procedure readiness, reorder lines, and usage/cost
rows for operational views.

Run the local Streamlit view after a Gold run exists:

```bash
streamlit run streamlit_app.py
```

The app lists available Gold manifests in the sidebar, newest first. If no Gold
run exists yet, run the full pipeline command below first.

## Full Pipeline Orchestration

Run the complete local pipeline with one command:

```bash
python3 -m orchestration.run_pipeline \
  --source-dir synthetic_data/generated \
  --event-count 250 \
  --movement-count 250 \
  --case-count 25 \
  --seed 42
```

The orchestrator regenerates synthetic source files by default, ingests them to
Bronze, transforms through Silver A and Silver B, publishes Gold outputs, and
writes an end-to-end manifest to `data_lake/pipeline_manifests/<run_id>.json`.
Use `--no-regenerate-sources` to run the pipeline from files already present in
the source directory.

## Pipeline Quality Gates

Evaluate a completed pipeline run before using it operationally:

```bash
python3 -m orchestration.quality_gates \
  --pipeline-manifest data_lake/pipeline_manifests/<run_id>.json
```

Quality gates verify that stage manifests exist, stage record counts are
non-empty, Silver A invalid rows are within threshold, required Silver B tables
exist, and required Gold dashboard artifacts were published. Results are written
to `data_lake/quality/manifests/<run_id>.json`. The command exits non-zero when
any required gate fails.

## MinIO and Docker Preview

Run the stock pipeline, quality gates, MinIO artifact publish, and Streamlit UI
with Docker Compose:

```bash
docker compose up --build stock_pipeline stock_quality stock_publish stock_streamlit
```

The Streamlit dashboard is exposed on `http://localhost:8502` by default. MinIO
is exposed on `http://localhost:9011` with the local development credentials in
`.env.example`. The pipeline writes local run outputs to `data_lake/`, then
`orchestration.publish_run_artifacts` publishes the manifests and output files
to MinIO under `stock_inventory/runs/<run_id>/`.

The Docker dashboard reads Gold artifacts back from MinIO by setting
`STOCK_DASHBOARD_STORAGE_MODE=object_store`. Local development without Docker
continues to read Gold manifests directly from `data_lake/gold/manifests/`.

The default Docker run id is `run_docker_preview`. Use a new run id when running
the compose job repeatedly:

```bash
STOCK_PIPELINE_RUN_ID=run_$(date +%Y%m%d_%H%M%S) docker compose up --build stock_pipeline stock_quality stock_publish
```
