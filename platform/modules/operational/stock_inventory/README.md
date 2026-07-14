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
python3 generate_synthetic_data/main_synthetic_stock_generator.py \
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
```

Stock positions enrich lots with catalogue, location, ERP balance, expiry,
recall, sterility, reorder, and value fields. Case readiness compares upcoming
case demand with available stock and flags ready, shortage, or substitution
available states.

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
inventory_risk_summary.json
```
