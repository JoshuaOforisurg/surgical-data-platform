# Surgeon Preference Card Data Product

This module is the surgeon preference-card data product within the wider
surgical data platform. It converts messy source records into clinically
enriched, versioned operational cards and provides a controlled Streamlit
workflow for viewing, drafting, reviewing, and publishing changes.

The public demonstration is available at
[www.surgeonpreference.com](https://www.surgeonpreference.com). It uses
synthetic data and must not be used to collect patient-identifiable or
confidential hospital information.

For commands, environment configuration, storage paths, and deployment
instructions, use [`README.md`](README.md). This document provides the concise
product and architecture overview.

## Current Status

Version 1 is complete as a standalone operational data product. It supports:

- clinically aligned synthetic source-data generation at 1000-file scale;
- local files, directories, and object-storage keys or prefixes as inputs;
- Landing, Bronze, Silver A, Silver B, and Gold processing;
- clinical reference matching, validation, readiness states, and quarantine;
- audit, catalogue, workflow, and user-registry metadata in PostgreSQL;
- MinIO locally and Azure Blob Storage in cloud deployments;
- versioned operational and analytics Gold artifacts;
- a Dockerized Streamlit application and dedicated batch-job image; and
- Azure Data Factory-triggered Azure Container App Job execution.

Version 2 is in progress. Its current foundation includes:

- Azure-managed identity integration through forwarded authentication headers;
- application users, organisations, memberships, and access requests;
- role-controlled draft submission, human review, and publishing;
- organisation identifiers on workflow and audit payloads; and
- separate editor, reviewer, administrator, and authenticated-user roles.

The current deployment still uses one default organisation. Full tenant
isolation has not yet been completed or validated for clinical use.

## Implemented Architecture

```text
Synthetic, uploaded, or object-storage source files
        |
        v
Object storage landing/{run_id}/
        |
        v
PostgreSQL Bronze ledger and metadata catalogue
        |
        v
Silver A: structural cleanup and schema flattening
        |
        v
Silver B: clinical resolution, validation, and quarantine
        |
        +------------------------------+
        |                              |
        v                              v
Gold operational cards         Gold analytics snapshot
        |
        v
Streamlit view, draft, review, publish, access, and metadata screens
```

The authoritative batch entry point is `main_orchestrator.py`. It delegates to
`orchestration/minio_medallion_pipeline.py`, which owns the current end-to-end
pipeline.

## Pipeline Responsibilities

### Source generation and ingestion

The synthetic generator creates clinically aligned orthopaedic preference
cards and can introduce controlled messiness for testing. The pipeline can
process aggregate files or one structured JSON/CSV file per card.

Each source file is checksummed, copied to a run-specific landing prefix, and
registered in PostgreSQL before its records are transformed.

### Silver A: structural normalization

Silver A accepts nested and flat record shapes, cleans text and codes, and
flattens the source into a consistent intermediate representation. It
preserves instruments, implants, equipment, consumables, and other structured
items for later clinical processing.

### Silver B: clinical enrichment

Silver B resolves procedures and instrument systems against the shared
clinical reference service. It checks procedure/system compatibility, expected
items, malformed quantities, and procedure-specific instructions.

Each record receives clinical flags, missing-item information, a confidence
score, and one of these frontline readiness states:

```text
Ready
Check before use
Review required
```

Records with critical anomalies are retained and routed to quarantine rather
than silently discarded.

### Gold data products

The operational Gold output contains one current card per surgeon/procedure
combination. Duplicate candidates are resolved using version, update time, and
confidence. The analytics Gold output summarizes the processed clinical data.

Both immutable run artifacts and replaceable `latest` views are published:

```text
gold/operational/runs/{run_id}/
gold/operational/latest/
gold/analytics/runs/{run_id}/
gold/analytics/latest/
```

## Controlled Product Workflow

The Streamlit app reads the latest operational Gold dataset. Published cards
are not directly edited in place.

```text
Editor submits a draft
        |
        v
Reviewer approves, rejects, or requests changes
        |
        v
Administrator publishes an approved draft
        |
        v
Gold is updated, versioned, and audited
```

Draft submissions, reviews, and publishing are controlled independently by
deployment feature flags. Public users can view synthetic demo cards but
cannot mutate published data.

Application roles are deliberately separated:

| Role | Product permission |
| --- | --- |
| `authenticated` | Signed-in identity without mutation rights |
| `editor` | Create and submit preference-card drafts |
| `reviewer` | Review submitted drafts |
| `admin` | Publish approved drafts and manage user access |

Azure Container Apps Authentication or Microsoft Entra ID should authenticate
users. This application does not store or manage passwords.

## Storage and Metadata

The object-storage interface selects the provider at runtime:

- MinIO/S3-compatible storage for local development;
- Azure Blob Storage when `AZURE_STORAGE_CONNECTION_STRING` is configured.

PostgreSQL stores searchable operational metadata across these areas:

- raw-file and raw-record ingestion;
- pipeline execution and Gold artifact audit;
- object-storage catalogue entries;
- Iceberg catalogue bootstrap metadata; and
- organisations, users, memberships, access requests, reviews, and audit events.

The Postgres-backed Iceberg catalogue and warehouse URI are bootstrapped, but
Silver and Gold are not yet persisted as Iceberg tables. The active production
path still publishes file-based Gold artifacts to object storage.

## Local and Azure Runtime

The local Docker Compose environment contains:

- PostgreSQL 16;
- MinIO;
- the batch pipeline; and
- the Streamlit web application.

The implemented Azure shape is:

| Local responsibility | Azure implementation |
| --- | --- |
| MinIO | Azure Blob Storage |
| PostgreSQL container | Azure Database for PostgreSQL Flexible Server |
| Pipeline container | Azure Container App Job |
| Streamlit container | Azure Container App |
| Manual/scheduled execution | Azure Data Factory trigger |
| Local image | Azure Container Registry image |

## FHIR and EPR Integration

FHIR integration is an early adapter capability, not the primary production
input path. The current adapter maps a FHIR R4-style bundle containing a
`ServiceRequest`, `Appointment`, and `Practitioner` into an internal
`procedure_scheduled` event.

The intended future boundary is:

```text
EHR/FHIR clinical event
        -> FHIR adapter
        -> internal preference event
        -> existing enrichment and operational-card services
```

FHIR supplies clinical and scheduling context. Theatre-specific instruments,
consumables, positioning, preparation, and surgeon preferences remain part of
the internal product model.

## Current Product Boundary

This is a synthetic-data product and learning platform. It is not currently
approved for real patient data or confidential hospital preference cards.
Before clinical deployment, the platform still needs at least:

- proven tenant and organisation isolation;
- data-processing and information-governance agreements;
- formal clinical safety review and hazard controls;
- production backup, restore, retention, and deletion procedures;
- security, monitoring, alerting, and incident-response validation;
- end-to-end Azure role and access testing; and
- a defined process for clinical catalogue ownership and approval.

## Where Development Is Heading

The immediate direction is to consolidate and harden the Version 2 controlled
workflow rather than expand the old Kardex concept. The wider platform now also
contains a stock/inventory data product. The two products can eventually
combine preference demand with inventory availability to support theatre
readiness, shortage detection, substitutions, and reorder planning.

Likely next engineering milestones are:

1. validate the full authenticated access-request, draft, review, and publish
   journey in Azure;
2. strengthen organisation isolation and enforce it consistently at storage
   and database boundaries;
3. add production-grade workflow state consistency and publishing rollback;
4. persist selected medallion outputs as managed Iceberg tables where that
   provides a real platform benefit;
5. define the contract between surgeon preferences and stock/inventory; and
6. expand FHIR integration only after the standalone operational workflow is
   stable and governed.

## Key Files

```text
main_orchestrator.py                         primary batch CLI
orchestration/minio_medallion_pipeline.py   end-to-end medallion pipeline
silver_transform/silver_a/                  structural normalization
silver_transform/silver_b/                  clinical enrichment and quarantine
gold_cleaned/                               operational and analytics products
domain/clinical_reference_service.py        clinical reference contract
storage/object_store.py                     MinIO/Azure storage abstraction
bronze_Ingestion/catalog.py                 Postgres metadata and workflow repository
app.py                                      Streamlit product interface
streamlit_services/                         access, drafts, review, and publishing
adapters/fhir_adapter.py                    initial FHIR event adapter
sql/azure_postgres_bootstrap.sql            Azure/Postgres schema bootstrap
tests/                                      clinical and workflow regression tests
```
