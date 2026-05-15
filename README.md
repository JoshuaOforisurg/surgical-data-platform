Below is a clean, upgraded README that:

- Keeps your clinical context and existing modules  
- Adds local + Azure cloud modes 
- Introduces a clear IaC layer  
- Updates repo structure to include infrastructure  



---

# Surgical Data Platform

## Description

This platform is a unified, modular data platform for operating theatre operations, intelligence, and AI training.

From my personal experience working in the operating theatre, I found the "hidden" cost of care is often found in disjointed systems and manual, inconsistent documentation. This platform is designed from a clinical perspective to address these needs and create a single unified architecture that supports:

- Real-time theatre operations  
- Analytics and intelligence  
- AI and robotics training data  

All modules follow the same engineering lifecycle and share a common core.

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
- or **Bicep (Azure-native)

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

The platform switches between local and cloud execution using an environment variable:

```bash
MODE=local   # local development
MODE=cloud   # Azure deployment
```

Pipelines share the same business logic but use different backends depending on the mode.

---

## Repository structure

```bash
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

## Author

GitHub: **JoshuaOforisurg**
