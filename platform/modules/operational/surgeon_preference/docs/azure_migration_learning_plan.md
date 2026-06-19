# Azure Migration Learning Plan

This project should move to Azure in two phases:

1. Standalone medallion pipeline
2. EHR-integrated pipeline with a FHIR adapter

The goal is not to rush deployment. The goal is to understand what each local
component becomes in Azure, prove the clinical safety gates locally, and then
migrate one responsibility at a time.

## Current Local Architecture

The current pipeline already has the right cloud shape:

```text
Synthetic/uploaded source file
    -> MinIO landing object
    -> Postgres metadata catalogue
    -> Silver-A structural cleanup
    -> Silver-B clinical enrichment and validation
    -> Gold operational card and analytics outputs
    -> Streamlit reads latest trusted Gold data
```

Local-to-Azure mapping:

| Local component | Azure equivalent | Learning purpose |
| --- | --- | --- |
| Docker Compose | Azure deployment environment | Learn how services become managed resources |
| MinIO | Azure Blob Storage or Azure Data Lake Storage Gen2 | Learn object storage, containers, prefixes, lifecycle |
| Local Postgres container | Azure Database for PostgreSQL Flexible Server | Learn managed relational metadata storage |
| Streamlit container | Azure Container Apps or App Service | Learn app hosting and environment variables |
| Pipeline container | Azure Container Apps Job, Azure Functions, or scheduled container | Learn repeatable compute for batch/event workloads |
| `.env` file | Azure Key Vault and Container App secrets | Learn secret handling |
| Local logs | Azure Monitor and Application Insights | Learn observability |

## Phase 1: Standalone Pipeline

Phase 1 keeps the system independent from an EHR.

Inputs:

- Streamlit-created draft preference cards
- Uploaded CSV/JSON/Excel files
- Synthetic data for safe development

Core learning objectives:

- Understand object storage by replacing MinIO concepts with Azure Blob Storage concepts.
- Understand managed Postgres by replacing the Docker database with Azure Database for PostgreSQL.
- Understand container deployment by running Streamlit and the pipeline as Azure-hosted containers.
- Understand secrets by moving credentials out of `.env`.
- Understand auditability by checking the Postgres metadata catalogue after every run.

Minimum Phase 1 Azure target:

```text
Azure Blob Storage landing/bronze/gold
Azure Database for PostgreSQL metadata catalogue
Azure Container App for Streamlit
Azure Container App Job for pipeline execution
Azure Key Vault or Container App secrets for credentials
Azure Monitor logs
```

Phase 1 clinical release gate:

Before a Gold output is trusted, the pipeline should prove:

- Clinical reference catalogue is valid.
- Postgres metadata catalogue is reachable and schema-valid.
- Bronze files were registered.
- Silver-B enrichment completed.
- Quarantine count is visible.
- Review-required records are counted.
- Gold operational row count is non-zero.
- Gold analytics source count matches source records processed.
- Data product and schema versions are recorded.

## Phase 2: EHR/FHIR-Integrated Pipeline

The original README describes two parallel pipelines:

- Standalone pipeline with no EPR integration
- EPR-integrated pipeline from a simulated Cerner/Epic feed

That idea is still right. The improvement is to make the EHR-integrated path
FHIR-first.

Important design principle:

FHIR is the integration language at the edge of the system. It should not erase
the internal surgeon preference card domain model.

In practice:

```text
EHR/FHIR event
    -> FHIR adapter
    -> internal canonical preference-card event
    -> existing validation/enrichment pipeline
    -> Postgres audit and Gold outputs
```

## Why FHIR

FHIR is the healthcare data exchange standard used by modern EHR integrations.
Azure Health Data Services includes a managed FHIR service, which provides a
FHIR API secured with Microsoft Entra ID.

Use Azure Health Data Services FHIR service for future learning and design.
Avoid starting new work on the older Azure API for FHIR product because Microsoft
has announced its retirement.

## What FHIR Should Represent

Surgeon preference cards are not a perfect one-resource fit in core FHIR.
Trying to force the whole preference card into one FHIR resource too early will
make the design brittle.

Instead, use FHIR to represent the clinical context and triggering event.

Likely FHIR resources:

| FHIR resource | Why it matters here |
| --- | --- |
| `Patient` | Identifies the patient for an operative pathway. Avoid storing unnecessary PHI in this module. |
| `Practitioner` | Represents the surgeon. |
| `PractitionerRole` | Represents surgeon role, specialty, organisation, or location context. |
| `Encounter` | Represents the hospital episode or theatre attendance context. |
| `Appointment` | Represents scheduled theatre activity before an encounter exists. |
| `ServiceRequest` | Represents a requested operation or procedure. |
| `Procedure` | Represents the completed operation. |
| `DeviceRequest` | Can represent requested implant/device needs when appropriate. |
| `DocumentReference` | Can reference a generated Kardex/preference-card PDF or document artifact. |
| `Provenance` | Records where a FHIR-derived preference-card event came from. |
| `AuditEvent` | Records access and changes around clinical data exchange. |

For preference-card-specific content such as trays, consumables, drapes,
positioning, and surgeon-specific instructions, keep an internal canonical
model. Later, if needed, represent that model as a FHIR profile or a
`DocumentReference` plus structured extensions.

## FHIR Adapter Responsibilities

The adapter should do four jobs:

1. Accept FHIR resources or bundles.
2. Extract only the fields the preference-card pipeline needs.
3. Map those fields to the internal canonical event.
4. Preserve provenance and raw payload references for audit.

Example internal event shape:

```json
{
  "event_type": "procedure_scheduled",
  "source_system": "ehr_fhir",
  "source_message_id": "ServiceRequest/example-id",
  "patient_ref": "Patient/123",
  "encounter_ref": "Encounter/456",
  "surgeon_ref": "Practitioner/789",
  "procedure_text": "Total Knee Replacement",
  "procedure_code": "W40.1",
  "laterality": "left",
  "scheduled_start": "2026-07-01T09:00:00Z",
  "raw_fhir_resource_refs": [
    "ServiceRequest/example-id",
    "Appointment/example-id"
  ]
}
```

That event can then pass into the current Silver-A/Silver-B/Gold pipeline.

## Recommended Learning Sequence

### Lesson 1: Explain the Local System

You should be able to say:

> My pipeline lands source files, audits them in Postgres, transforms them
> through bronze/silver/gold, validates clinical safety, and publishes trusted
> Gold outputs for Streamlit.

Practice:

- Run `python3 main_orchestrator.py --check-postgres`.
- Open the Streamlit Metadata tab.
- Explain each Postgres section in plain English.

### Lesson 2: Understand Azure Storage

Learn:

- Storage account
- Container
- Blob
- Prefix
- Data Lake hierarchical namespace

Map:

```text
MinIO bucket surgical-data
    -> Azure Storage account + container

landing/run_id/file.json
    -> Azure blob path
```

Do not migrate first. First, draw the mapping.

### Lesson 3: Understand Managed Postgres

Learn:

- Flexible Server
- Database
- Firewall/private access
- User roles
- Connection string
- Backups

Map:

```text
surgeon_preference_postgres container
    -> Azure Database for PostgreSQL Flexible Server
```

First migration exercise:

- Create an empty Azure PostgreSQL database.
- Run only the metadata schema initialization.
- Run the health check.
- Do not move PHI or real clinical data during early learning.

### Lesson 4: Understand Containers

Learn:

- Container image
- Container registry
- Environment variable
- Secret
- Revision
- Log stream

Map:

```text
streamlit_app service
    -> Azure Container App

surgeon_pipeline service
    -> Azure Container App Job
```

### Lesson 5: Understand FHIR

Start with test bundles, not a live EHR.

Build:

- `examples/fhir/procedure_scheduled_bundle.json`
- `adapters/fhir_adapter.py`
- tests that map FHIR into an internal event

First adapter target:

```text
FHIR ServiceRequest + Appointment + Practitioner
    -> procedure_scheduled internal event
```

Only after that should you connect to Azure Health Data Services.

## What Not To Do Yet

Avoid these until the basics are clear:

- Do not connect a live EHR.
- Do not store real patient identifiers in development data.
- Do not make Azure the only place the pipeline can run.
- Do not force all preference-card fields into FHIR resources prematurely.
- Do not skip audit/provenance.

## Pre-Cloud Improvement Backlog

Before the first Azure deployment, add:

- A clinical release gate report.
- A FHIR adapter skeleton.
- A sample FHIR bundle.
- A `--dry-run` mode for the pipeline.
- A visible quarantine summary in Streamlit.
- A README section explaining the two phases.

## Sources For Learning

- Azure Health Data Services FHIR service:
  https://learn.microsoft.com/en-us/azure/healthcare-apis/fhir/overview
- Azure Blob Storage:
  https://learn.microsoft.com/en-us/azure/storage/blobs/storage-blobs-introduction
- Azure Data Lake Storage hierarchical namespace:
  https://learn.microsoft.com/en-us/azure/storage/blobs/data-lake-storage-namespace
- Azure Database for PostgreSQL:
  https://learn.microsoft.com/en-us/azure/postgresql/overview
- Azure Container Apps:
  https://learn.microsoft.com/en-us/azure/container-apps/overview
- Azure Well-Architected Framework:
  https://learn.microsoft.com/en-us/azure/well-architected/
- HL7 FHIR R4:
  https://hl7.org/fhir/R4/
