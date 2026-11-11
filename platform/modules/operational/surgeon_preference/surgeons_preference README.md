# Surgeon Preference

Surgeon Preference is an operational data product for theatre teams to find
current preference cards and manage proposed updates through a controlled
human-review workflow. Its data pipeline validates and versions card data for
the application. The current interface is Streamlit. The product uses
synthetic data and is not approved for real clinical use.

## Current Status

The repository contains a locally testable preference-card pipeline and a
tenant-aware workflow foundation. It is still being hardened and is not ready
for hospital onboarding, confidential hospital data, or clinical operation.

Implemented locally:

- Synthetic preference-card generation, including aggregate or partitioned
  structured input files.
- Landing, Bronze, Silver A, Silver B, and Gold processing with source
  checksums, run/file lineage, contract and quality checks, quarantine, and
  replay of failed pipeline runs.
- Clinical enrichment for procedure and instrument-system alignment, required
  items, and procedure-specific instructions.
- PostgreSQL-backed operational current cards, card versions, workflow state,
  user/organisation metadata, and pipeline catalogue metadata.
- MinIO object storage for landed inputs and versioned Silver/Gold artifacts.
- Streamlit synthetic demo and tenant-scoped workspace workflow.
- Membership-based roles and local two-organisation integration coverage.
- Draft, review, publish, history, and rollback workflows.

The default local workspace needs fresh end-to-end verification: the read-only
verifier currently finds that the latest PostgreSQL run references a missing
MinIO manifest. Do not present the default local workspace as a freshly
verified run until it has been rerun and checked.

## Architecture

```text
Synthetic source files
                |
                v
Object storage landing -> Bronze records and lineage
                |
                v
Silver A structural normalization
                |
                v
Silver B clinical enrichment and validation
                |
          Contract + quality gates
                |
                v
Gold operational snapshots and analytics artifacts
                |
       +--------+---------+
       |                  |
       v                  v
PostgreSQL operational   MinIO versioned artifacts,
cards and versions      manifests, and pipeline data
       |
       v
Streamlit search, card view, and controlled change workflow
```

PostgreSQL is the operational source for current preference cards and their
versions. MinIO stores source files and pipeline artifacts, including
versioned Gold exports. PostgreSQL bootstraps Iceberg catalogue metadata, but
current Silver and Gold outputs are files, not persisted Iceberg tables.

## Human Approval Workflow

```text
Authorised member proposes a draft
                |
                v
A different authorised reviewer approves, rejects, or requests changes
                |
                v
Authorised publisher publishes an approved draft as a new version
```

The submitter cannot review their own draft. Approval alone does not make the
draft current; an authorised publisher must publish it. Decisions and
published versions are auditable. Automation may validate or suggest a change,
but cannot bypass human review or approval.

Local identity and organisation workflows remain a prototype. Workspace
creation can currently grant the creator initial administrator access;
production onboarding still needs sponsor verification, controlled invitations,
and recovery/abuse controls. Google or other federated sign-in would establish
identity, not hospital membership or permissions.

## Run Locally

Requirements: Docker Compose and Python 3.12 or newer. Keep local credentials
in an ignored `.env` file. Never put secrets, access tokens, or production
connection strings in this README or in Git.

1. Create `.env` from `.env.example` and set local-only PostgreSQL and MinIO
   passwords.
2. Start the stack from this directory:

   ```bash
   docker compose up --build
   ```

   Compose starts PostgreSQL and MinIO, runs the synthetic pipeline, then
   starts Streamlit after a successful pipeline run.
3. Open `http://localhost:8501`. The public preview uses synthetic cards.
   PostgreSQL is exposed on host port `5433`; MinIO uses ports `9000` and
   `9001` for its API and console.
4. Stop with `Ctrl-C`. `docker compose down` removes containers but retains
   persistent database and object-store data in Compose volumes.

For local development outside Compose, install dependencies with Poetry and
start PostgreSQL and MinIO, then run:

```bash
poetry run python main_orchestrator.py --synthetic-count 1000
poetry run streamlit run app.py --server.address=127.0.0.1 --server.port=8501
poetry run pytest tests -q
```

Use `tests` explicitly: unqualified pytest from the repository root may
discover unrelated vendored test files. Two integration tests use disposable
local Postgres/MinIO resources and are opt-in.

## Verification Snapshot

On 2026-11-11, the Surgeon Preference suite reported **228 passed, 2 skipped**;
both opt-in local integration tests passed when run separately. Stock Inventory
reported **43 passed** and Loan Kit Management **8 passed**. Tests use synthetic
data and do not establish cloud or clinical readiness.

## Current Boundaries

- Azure hosting, authentication, managed identity, and cloud storage/database
  operation are not currently verified; there is no hosted end-to-end evidence.
- PostgreSQL row-level security, immutable internal user IDs, account linking,
  stronger organisation onboarding, security review, and operational recovery
  controls remain outstanding.
- The default local workspace has a PostgreSQL-to-MinIO manifest mismatch;
  rerun and verify it before presenting it as a fresh successful pipeline run.
- Theatre Readiness is a target direction, not a unified operational worklist.
  Stock Inventory has its own case-readiness output; Loan Kit Management is an
  early synthetic pipeline skeleton.
- Stock and Loan Kit synthetic case identifiers do not align. Item mappings
  are incomplete, Stock has no declared Gold schema version, and Loan Kit does
  not yet provide itemized kit contents. A shared tested contract is required
  before joining these outputs.
- Do not enter patient-identifiable or confidential hospital preference data.
  The system does not replace physical theatre checks, sterilisation records,
  clinical judgment, or local governance.
- The FHIR adapter is an early mapping example, not a validated live EPR
  integration.

## Key Code Locations

| Area | Location |
| --- | --- |
| Application entry point | `app.py` |
| Pipeline CLI and settings | `main_orchestrator.py`, `config/` |
| Medallion orchestration | `orchestration/minio_medallion_pipeline.py` |
| Clinical domain and contracts | `domain/`, `contracts/` |
| Bronze ingestion and metadata catalogue | `bronze_Ingestion/` |
| Silver transformations | `silver_transform/` |
| Gold outputs | `gold_cleaned/` |
| UI-independent workflow services | `application_services/` |
| Storage abstraction | `storage/`, shared `platform/shared/storage/` |
| Streamlit services and renderers | `streamlit_services/`, `streamlit_renderers/` |
| Tests | `tests/` |
