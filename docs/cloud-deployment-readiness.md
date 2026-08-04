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

`.github/workflows/container-images.yml` builds the Streamlit and batch-job
container images for both modules. Pull requests build without pushing. Pushes
to `main`, and manual dispatches with `push_images=true`, push images to GHCR.

## Live Container Validation

The preflight does not replace a real container run. Before calling the product
cloud-ready, validate both local stacks with Docker.

Preferred repeatable smoke:

```bash
python3 scripts/container_smoke_validation.py
```

This runs the stock pipeline, quality gates, artifact publish, object-store
dashboard read, surgeon pipeline, and both Streamlit health checks. Use
`--skip-stock` or `--skip-surgeon` when validating one module at a time.

Stock inventory:

```bash
cd platform/modules/operational/stock_inventory
export STOCK_PIPELINE_RUN_ID=run_$(date +%Y%m%d_%H%M%S)
docker compose up -d stock-minio
docker compose run --rm stock_pipeline
docker compose run --rm --no-deps stock_quality
docker compose run --rm --no-deps stock_publish
docker compose up -d --build --no-deps stock_streamlit
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

If local port `8501` is already used by a non-container Streamlit process, run
the surgeon smoke UI on another host port. The smoke script uses `8503` for
this reason.

## Latest Validation Record

Validated locally on August 3, 2026:

```text
Cloud deployment preflight with tests: passed
Stock Docker pipeline: passed
Stock quality gates: passed
Stock MinIO publish: passed
Stock Streamlit health: passed on http://localhost:8502
Stock object-store dashboard snapshot: passed
Surgeon Docker pipeline: passed
Surgeon Streamlit health: passed on http://localhost:8503
```

The surgeon preference smoke used the local `.env` runtime configuration. In
the current laptop environment, that points storage at Azure Blob/Iceberg and
therefore validates a cloud-style storage path as well as Docker execution.

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
GitHub Actions container image build/push scaffold
Cloud runtime env templates
Repeatable Docker smoke validation script
```

The remaining blockers before production cloud migration are:

```text
Cloud object storage and Postgres secrets configured in the target platform
Target deployment manifests for the chosen cloud runtime
End-to-end smoke test against managed storage and database services
Stock Azure Blob adapter if the target cloud must be pure Azure Blob rather
than an S3-compatible object store
Observability, alerting, rollback, and release approval policy
```
