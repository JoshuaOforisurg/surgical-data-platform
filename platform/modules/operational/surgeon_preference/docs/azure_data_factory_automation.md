# Azure Data Factory Automation

This phase turns the working Azure Blob migration into an automated cloud
pipeline.

## Target Flow

```text
ADF starts the scheduled/manual test run
        |
        v
Azure Data Factory trigger starts
        |
        v
Container App Job runs the pipeline image
        |
        v
Pipeline generates 1000 partitioned synthetic source files
        |
        v
Pipeline writes managed outputs:
landing/
bronze/
gold/operational/latest/
gold/analytics/latest/
        |
        v
Streamlit reads gold/operational/latest/
```

Use `incoming/` later for user or EHR uploads. Do not trigger on `landing/`,
because the pipeline writes to `landing/` itself.

## Container Command

Use the dedicated job image for automation. For the current learning/dev
workflow, it generates a realistic 1000-file synthetic batch and then runs the
normal medallion pipeline:

```bash
python main_orchestrator.py \
  --synthetic-count 1000 \
  --synthetic-output-mode partitioned \
  --synthetic-file-formats json,csv
```

This creates 1000 individual source files inside the container, alternating
between JSON and CSV, then lands and processes them in one run. A later dynamic
event-driven version can use `--source-object-prefix incoming/` or
`--source-object-key incoming/{file}` when the pipeline should process uploaded
or EHR-triggered files instead of generating synthetic data.

## Required Environment Variables

The Container App Job needs the same secrets as the web app:

```text
AZURE_STORAGE_CONNECTION_STRING
AZURE_CONTAINER_NAME
DB_HOST
DB_PORT
DB_USER
DB_NAME
DB_PASSWORD
```

The image can keep MinIO variables for local fallback, but Azure mode is chosen
when `AZURE_STORAGE_CONNECTION_STRING` is present.

## First Manual Test

1. Start the Container App Job from ADF or manually in Azure.
2. Confirm Azure Blob contains fresh objects under:

```text
landing/
bronze/
gold/operational/latest/
gold/analytics/latest/
```

3. In `landing/{run_id}/`, confirm there are many generated source files.
4. Open Streamlit and confirm it loads the latest Gold operational card file.
5. Query Postgres and confirm the latest run registered many source files:

```sql
select run_id, original_filename, object_key, created_at
from bronze_raw.ingested_files
order by created_at desc
limit 20;
```

## ADF Setup

Start simple:

1. Create a Data Factory.
2. Add an Azure Blob Storage linked service for the same storage account.
3. Start with a manual or scheduled trigger for synthetic batch testing.
4. Add a pipeline activity that starts the Container App Job.
5. Start with the job image default command, which generates and processes the
   1000-file synthetic batch. Later, pass the incoming blob path or prefix
   dynamically when you want event-level upload processing.

After that works, add failure alerts and a quarantine path for invalid uploads.
