# Cloud Deployment Readiness

This project is moving from local data-product demos toward deployable platform
services. A cloud-ready change should prove three things before it is merged:

1. The Python source compiles without relying on local IDE or virtualenv state.
2. Docker Compose files are syntactically valid with runtime secrets supplied
   through environment variables.
3. The stock pipeline can pass a cloud-like object-store preflight, and focused
   module tests pass in CI.

## Local Preflight

Run from the repository root:

```bash
python3 scripts/cloud_deployment_preflight.py
```

Run the fuller version when `pytest` and module dependencies are available:

```bash
python3 scripts/cloud_deployment_preflight.py --include-tests
```

If Docker is temporarily unavailable on the laptop, use:

```bash
python3 scripts/cloud_deployment_preflight.py --skip-docker
```

Skipping Docker is acceptable for local diagnosis only. A PR is not ready for
cloud migration until Docker Compose validation passes in CI or on another
machine with Docker available.

## CI Gate

`.github/workflows/platform-readiness.yml` runs on pull requests, pushes to
`main`, and manual dispatch. It installs the stock and surgeon preference
dependencies, then runs:

```bash
python scripts/cloud_deployment_preflight.py --include-tests
```

This gives every cloud-facing PR the same minimum gate:

```text
Python syntax check
Stock Docker Compose config
Surgeon Preference Docker Compose config
Stock cloud-like object-store preflight
Stock module tests
Focused Surgeon Preference workflow tests
```

## Live Container Validation

The preflight does not replace a real container run. Before calling the product
cloud-ready, validate both local stacks with Docker.

Stock inventory:

```bash
cd platform/modules/operational/stock_inventory
STOCK_PIPELINE_RUN_ID=run_$(date +%Y%m%d_%H%M%S) \
  docker compose up --build stock_pipeline stock_quality stock_publish stock_streamlit
```

Surgeon preference:

```bash
cd platform/modules/operational/surgeon_preference
cp .env.example .env
# Fill DB_PASSWORD and MINIO_ROOT_PASSWORD in .env with local development values.
docker compose up --build
```

Expected local endpoints:

```text
Surgeon Preference Streamlit: http://localhost:8501
Stock Inventory Streamlit:   http://localhost:8502
Stock MinIO console:         http://localhost:9011
```

## Cloud Secrets And Runtime Inputs

Never commit production secrets. Supply these through the deployment platform's
secret manager.

Stock inventory:

```text
MINIO_ENDPOINT or managed S3-compatible endpoint
MINIO_ROOT_USER or MINIO_ACCESS_KEY
MINIO_ROOT_PASSWORD or MINIO_SECRET_KEY
MINIO_BUCKET
MINIO_ROOT_PREFIX
STOCK_DASHBOARD_STORAGE_MODE=object_store
STOCK_PIPELINE_SOURCE_DIR
SURGEON_PREFERENCE_GOLD_PATH
```

Surgeon preference:

```text
AZURE_STORAGE_CONNECTION_STRING or managed object-store credentials
AZURE_CONTAINER_NAME
POSTGRES_HOST or DB_HOST
POSTGRES_PORT or DB_PORT
POSTGRES_USER or DB_USER
POSTGRES_PASSWORD or DB_PASSWORD
POSTGRES_DB or DB_NAME
APP_ORGANISATION_ID
APP_ORGANISATION_NAME
```

## Current Cloud Status

The platform now has the foundations needed to approach cloud migration:

```text
Dockerized Streamlit apps
Dockerized batch jobs
Local MinIO/Postgres preview services
Object-store publishing and dashboard reads
Cross-pipeline stock readiness analytics
Organisation-scoped surgeon workflow metadata
Root cloud deployment preflight
GitHub Actions readiness gate
```

The remaining blockers before production cloud migration are:

```text
Successful live Docker Compose run on a responsive Docker daemon
Cloud object storage and Postgres secrets configured in the target platform
Container registry build and push automation
Target deployment manifests for the chosen cloud runtime
End-to-end smoke test against managed storage and database services
```
