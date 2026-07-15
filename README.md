# Surgical Data Platform

## Portfolio Snapshot

This repository is a healthcare data engineering portfolio project built from
real operating theatre experience. It demonstrates how surgical workflow
problems can be translated into modular data pipelines, auditable data products,
and cloud-deployed operational tools.

The first completed module is the **Surgeon Preference Pipeline**, a version 1
operational data product that processes synthetic surgeon preference data
through landing, bronze, silver, and gold layers, publishes preference-card
outputs, and serves them through a Dockerized Streamlit app running on Azure.

Live demo: [www.surgeonpreference.com](https://www.surgeonpreference.com)

> This project uses synthetic data only. It does not contain real patient data,
> staff data, theatre lists, or hospital confidential information.

## Description

This platform is a unified, modular data platform for operating theatre operations, intelligence, and AI training.

From my personal experience working in the operating theatre, I found the "hidden" cost of care is often found in disjointed systems and manual, inconsistent documentation. This platform is designed from a clinical perspective to address these needs and create a single unified architecture that supports:

- Real-time theatre operations  
- Analytics and intelligence  
- AI and robotics training data  

All modules follow the same engineering lifecycle and share a common core.

## Why This Project Matters

Operating theatres generate valuable operational signals, but much of the work
is still fragmented across preference cards, stock checks, manual documents,
device systems, EHR events, and informal local knowledge. This platform explores
how data engineering can support safer and more efficient surgical operations
by making theatre data structured, traceable, and reusable.

The platform is intentionally built from a clinical operations perspective:

- surgeon preferences affect theatre readiness and case flow
- stock and implant availability affect delays and substitutions
- theatre utilisation depends on clean event and workflow data
- audit trails matter for clinical trust and operational review
- synthetic data is needed for safe development before real integrations

---

## Current module status

### Completed Version 1 modules

- **Surgeon Preference Pipeline**
  Version 1 is complete as a standalone operational data product. It now runs
  locally and in Azure, with a Dockerized Streamlit frontend, a dedicated
  Container App Job for scheduled/manual batch execution, Azure Blob Storage
  outputs, Azure Postgres metadata and audit tables, Azure Data Factory
  orchestration, and a secured custom domain.

  Current ingestion mode: scheduled/manual synthetic batch ingestion. The Azure
  job generates 1000 clinically aligned source files, processes them through
  landing, bronze, silver, and gold layers, and publishes the latest operational
  preference cards for review.

### Next planned module

- **Stock & Inventory Management Pipeline**
  This is the recommended next pipeline because it connects naturally to surgeon
  preferences. Surgeon preference cards describe expected procedure demand;
  inventory data will show actual consumable, implant, and tray availability.
  Together, both modules can support shortage detection, substitution review,
  reorder planning, and theatre readiness workflows.

---

## Completed Surgeon Preference Pipeline V1

The Surgeon Preference module currently demonstrates:

- synthetic clinical source generation at 1000-file scale
- JSON and CSV source ingestion
- landing, bronze, silver A, silver B, and gold processing
- clinical reference enrichment and validation
- FHIR example adapter for scheduled procedure messages
- PostgreSQL schemas for bronze metadata, pipeline audit, object catalogue, gold
  artifact tracking, and Iceberg catalogue bootstrap
- cloud-agnostic object storage abstraction for local MinIO and Azure Blob
- Dockerized Streamlit frontend for operational preference-card review
- dedicated Dockerized batch job image for pipeline execution
- Azure Blob Storage, Azure PostgreSQL, Azure Container Registry, Azure
  Container Apps, and Azure Data Factory orchestration learning path
- custom-domain deployment and revision/image troubleshooting

Current ingestion mode is scheduled/manual synthetic batch ingestion. The next
engineering milestone is to connect the Surgeon Preference output to a Stock &
Inventory Management pipeline so preference-card demand can be compared against
stock, implant, tray, and supplier availability.

---

## Platform architecture

### Core layer

Shared functionality used by all modules:

- **Ingestion**  
- **Validation**  
- **Logging**  
- **Scheduling**  
- **Storage**  
- **Utilities**

---

### Module layer (pipeline categories)

#### Operational modules

Core pipelines that support day-to-day theatre operations:

- **Case Scheduling** (booking, lists, cancellations, overruns)  
- **Surgeon Preference** (procedure cards, pick lists)  
- **Instrument & Tray Tracking** (sterilisation, location, usage history)  
- **Loan Kit & Instrument Management** (vendor coordination, availability, returns)  
- **Anaesthetic Workflow** (pre-op, intra-op, recovery data)  
- **Stock & Inventory Management** (consumables, implants, auto-replenishment)  
- **Patient Pathway Tracking** (pre-op → theatre → recovery → discharge)  
- **Theatre Workflow Orchestration** (case progress, status updates, delays)  
- **Clinical Coding Support** (pipelines that process theatre data and help coders code faster)

#### Intelligence modules

Pipelines that provide analytics-ready data for theatre insights:

- **Theatre Utilisation** (room usage, idle time, block utilisation)  
- **Turnaround Time** (case-to-case efficiency, bottlenecks)  
- **Staffing Efficiency** (rosters vs actual demand, skill mix)  
- **Brief & Debrief Compliance** (checklists, safety signals)  
- **Cancellation & Delay Analysis** (root causes, trends)  
- **Cost Per Case** (linking consumables, staffing, time)  
- **Surgeon Performance Insights** (variation, duration benchmarks)  
- **Predictive Scheduling** (forecasting overruns, capacity planning)  
- **SurgiTrack Analytics** (tracking patient medical devices and implants for analytics)

#### AI & training modules

Pipelines that feed into ML models for surgical training and robotics:

- **Surgical Video Hub** (capture, storage, indexing, annotation)  
- **Procedure Segmentation** (AI labelling of surgical phases)  
- **Skills Assessment Models** (performance scoring, training feedback)  
- **Robotics Integration** (telemetry, motion data, system logs)  
- **Instrument Usage Analytics** (how tools are used during procedures)  
- **Simulation & Training Data** (synthetic or recorded training scenarios)

---

### Platform pipelines

“Glue” pipelines that connect the platform:

- **Data Integration Layer** (EHR, ERP, vendor systems, devices)  
- **Master Data Management** (patients, staff, instruments, procedures)  
- **Event Streaming / Real-Time Bus** (status updates across systems)  
- **Compliance & Audit Logging** (traceability, medico-legal requirements)  
- **Permissions & Access Control** (who sees what, especially video)  
- **Data Quality & Validation** (clean, consistent datasets)

---

### Shared layer

- **JSON schemas**  
- **Config files**  
- **Common models**

---

## Deployment modes

The platform supports two execution modes: **local** and **cloud (Azure)**.

### Local mode

Designed for rapid development and testing:

- Local JSON/CSV or SQLite storage  
- Local scheduler (cron / APScheduler)  
- Local logging  
- No cloud dependencies  
- Fast iteration and zero cost

Use this mode when developing pipelines, generating synthetic data, or testing schema validation.

---

### Cloud mode (Azure)

Designed for production-grade execution using Azure services.

#### Azure components

- **Azure Storage (Blob / ADLS Gen2)** — raw, validated, curated data layers  
- **Azure Functions** — ingestion, validation, event-driven triggers  
- **Azure Container Apps / AKS** — long-running or compute-heavy workloads  
- **Azure Event Grid / Service Bus** — real-time theatre workflow events  
- **Azure Key Vault** — secrets and credentials  
- **Azure Monitor / Application Insights** — logging, metrics, observability  
- **Azure SQL / Cosmos DB** — structured storage (future)

Cloud mode enables real-time, scalable, secure theatre data operations.

---

## Infrastructure-as-Code (IaC) layer

All Azure resources are provisioned using Infrastructure-as-Code to ensure reproducibility and consistent environments.

Recommended tools:

- Terraform (industry-standard, cloud-agnostic)  
- or **Bicep** (Azure-native)

#### IaC responsibilities

- Provision storage, compute, networking  
- Create dev/test/prod environments  
- Manage secrets and identity  
- Deploy event-driven architecture  
- Enforce consistent cloud deployments

Example structure:

```bash
infrastructure/
  terraform/        # or bicep/
    main.tf
    variables.tf
    outputs.tf
    modules/
```

---

## Mode switching

The Surgeon Preference pipeline currently switches storage backend from its
runtime environment:

```text
Local development: no AZURE_STORAGE_CONNECTION_STRING, so MinIO is used.
Azure deployment: AZURE_STORAGE_CONNECTION_STRING is set, so Azure Blob is used.
```

Pipelines share the same business logic but use different backends depending on
the configured environment variables.

---

## Repository structure

```text
theatre-data-platform/
├── README.md
├── docs/
│   ├── overview.md
│   ├── architecture.md
│   ├── modules.md
│   ├── data-models.md
│   └── roadmap.md
├── platform/
│   ├── core/
│   ├── operational/
│   ├── intelligence/
│   └── ai-training/
├── infrastructure/
│   └── terraform/        # or bicep/
└── tests/
```

---

## Platform lifecycle

All modules follow the same lifecycle:

1. Ingest  
2. Validate  
3. Transform  
4. Log
5. Load  
6. Schedule  
7. Document

---

## Roadmap

- Generate synthetic data and utilise data from public data sources  
- Transform data to ensure schema validation  
- Add FHIR/HL7 integration (where needed)  
- Add orchestration  
- Add dashboards  
- Add ML models  
- Add CI/CD  
- Add full Azure IaC and deployment scripts  

---

## Repository Hygiene And Security

- `.env` files are ignored and should never be committed.
- `.env.example` contains placeholders only.
- The project uses synthetic data for development and demonstration.
- Local secrets should be supplied through environment variables.
- Cloud secrets should be supplied through Azure Container App secrets or Azure
  Key Vault in a production setup.
- Generated caches, Mac system files, and local scratch files are excluded from
  the portfolio surface.

---

## Author

Joshua Ofori Donkor

- GitHub: **JoshuaOforisurg**
- Portfolio focus: surgical operations, biomedical science, theatre workflow,
  and healthcare data engineering
