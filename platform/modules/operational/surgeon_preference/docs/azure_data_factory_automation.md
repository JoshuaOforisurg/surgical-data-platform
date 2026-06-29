# Azure Data Factory Automation

This phase turns the working Azure Blob migration into an automated cloud
pipeline.

## Target Flow

```text
Upload source file to Azure Blob incoming/
        |
        v
Azure Data Factory trigger starts
        |
        v
Container App Job runs the pipeline image
        |
        v
Pipeline downloads incoming/{file}
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

Use `incoming/` for user or EHR uploads. Do not trigger on `landing/`, because
the pipeline writes to `landing/` itself.

## Container Command

The same Docker image can run the Streamlit app or the batch pipeline. For
automation, run this command inside a Container App Job:

```bash
python main_orchestrator.py --source-object-key incoming/master_preferences.json
```

For a dynamic ADF trigger, replace `incoming/master_preferences.json` with the
blob path supplied by the trigger event.

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

1. Upload a test file to Azure Blob:

```text
surgeon-preference/incoming/master_preferences.json
```

2. Run the container job with:

```bash
python main_orchestrator.py --source-object-key incoming/master_preferences.json
```

3. Confirm Azure Blob contains fresh objects under:

```text
landing/
bronze/
gold/operational/latest/
gold/analytics/latest/
```

4. Open Streamlit and confirm it loads the latest Gold operational card file.

## ADF Setup

Start simple:

1. Create a Data Factory.
2. Add an Azure Blob Storage linked service for the same storage account.
3. Add a trigger for new files under `incoming/`.
4. Add a pipeline activity that starts the Container App Job.
5. Pass the incoming blob path to the job command.

After that works, add failure alerts and a quarantine path for invalid uploads.
