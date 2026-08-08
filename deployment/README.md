# Deployment Scaffold

This folder records the first production deployment contract for the surgical
data platform. It does not contain real secrets and it does not provision cloud
resources by itself.

## Container Images

`.github/workflows/container-images.yml` builds these images from the shared
platform context:

```text
ghcr.io/<owner>/<repo>/surgeon-preference-app
ghcr.io/<owner>/<repo>/surgeon-preference-job
ghcr.io/<owner>/<repo>/stock-inventory-app
ghcr.io/<owner>/<repo>/stock-inventory-job
```

Pull requests build the images without pushing. Pushes to `main`, and manual
workflow dispatches with `push_images=true`, push versioned tags to GHCR.

## Runtime Shape

Surgeon preference:

```text
Container App:       surgeon-preference-app
Container App Job:   surgeon-preference-job
Object storage:      Azure Blob container
Metadata database:   Managed PostgreSQL
Secrets:             Container App secrets or Key Vault references
```

Stock inventory:

```text
Container App:       stock-inventory-app
Container App Job:   stock-inventory-job
Object storage:      Azure Blob container
Metadata database:   Azure Database for PostgreSQL
Secrets:             Container App secrets or Key Vault references
```

## Deployment Order

1. Run `python3 scripts/cloud_deployment_preflight.py --include-tests`.
2. Run `python3 scripts/container_smoke_validation.py` locally when Docker is
   available.
3. Merge to `main` so the image workflow builds and pushes GHCR images.
4. Provision managed storage and PostgreSQL for the target environment.
5. Create platform secrets from the templates in `deployment/runtime_env/`.
6. Deploy the job containers first and run a manual smoke job.
7. Deploy the Streamlit containers after the job outputs are readable from
   managed storage.
8. Run the cross-pipeline stock readiness flow after surgeon preference Gold is
   published.

## Storage Providers

Both operational modules support Azure Blob Storage for cloud deployments.
Stock inventory retains the local MinIO adapter for Docker development and
selects Azure Blob when `AZURE_STORAGE_CONNECTION_STRING` is supplied. Its
pipeline metadata is stored in PostgreSQL in both environments.
