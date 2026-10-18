# Surgical Data Platform

A healthcare data product built from real operating-theatre experience. The platform turns messy surgical operations data into governed pipelines, operational dashboards, audit trails, and readiness views that frontline theatre teams could actually use.

The current product focus is deliberately narrow:

```text
Surgeon Preference -> Stock Inventory -> Loan Kit Management -> Case Readiness
```

The project uses **synthetic data only**. It does not contain real patient data, staff records, theatre lists, hospital stock records, or confidential hospital information.

Live project site: [www.surgeonpreference.com](https://www.surgeonpreference.com)

## Start Here

| Need | Link |
| --- | --- |
| Product execution plan | [`platform/modules/operational/surgeon_preference/docs/three_pipeline_execution_plan.md`](platform/modules/operational/surgeon_preference/docs/three_pipeline_execution_plan.md) |
| Surgeon Preference overview | [`platform/modules/operational/surgeon_preference/surgeons_preference README.md`](platform/modules/operational/surgeon_preference/surgeons_preference%20README.md) |
| Tenant access contract | [`platform/modules/operational/surgeon_preference/docs/tenant_access_contract.md`](platform/modules/operational/surgeon_preference/docs/tenant_access_contract.md) |
| Local Phase 1 evidence | [`pipeline evidence`](platform/modules/operational/surgeon_preference/docs/evidence/phase1-local-pipeline.json) and [`workflow evidence`](platform/modules/operational/surgeon_preference/docs/evidence/phase1-local-workflow.json) |
| Surgeon Preference Postgres/DBeaver inspection | [`platform/modules/operational/surgeon_preference/docs/local_postgres_inspection.md`](platform/modules/operational/surgeon_preference/docs/local_postgres_inspection.md) |
| Preference-card rollback design | [`platform/modules/operational/surgeon_preference/docs/preference_card_rollback_design.md`](platform/modules/operational/surgeon_preference/docs/preference_card_rollback_design.md) |
| Real user access model | [`platform/modules/operational/surgeon_preference/docs/real_user_access_model.md`](platform/modules/operational/surgeon_preference/docs/real_user_access_model.md) |
| Productisation roadmap | [`platform/modules/operational/surgeon_preference/docs/productisation_roadmap.md`](platform/modules/operational/surgeon_preference/docs/productisation_roadmap.md) |
| Azure migration learning plan | [`platform/modules/operational/surgeon_preference/docs/azure_migration_learning_plan.md`](platform/modules/operational/surgeon_preference/docs/azure_migration_learning_plan.md) |
| Azure Data Factory automation notes | [`platform/modules/operational/surgeon_preference/docs/azure_data_factory_automation.md`](platform/modules/operational/surgeon_preference/docs/azure_data_factory_automation.md) |
| Stock Inventory module | [`platform/modules/operational/stock_inventory`](platform/modules/operational/stock_inventory) |
| Loan Kit module placeholder | [`platform/modules/operational/Loan Kit and Instrument Management`](platform/modules/operational/Loan%20Kit%20and%20Instrument%20Management) |
| Deployment notes | [`deployment/README.md`](deployment/README.md) |

This README gives the platform overview. The linked documents hold the deeper runbooks, design notes, and implementation plans.

## Product Vision

Operating theatres depend on the right information being correct at the right time: surgeon preferences, instruments, implants, consumables, stock, loan kits, sterility status, supplier milestones, and local team knowledge.

In many hospitals, this information is split across paper folders, spreadsheets, supplier messages, stock cupboards, scanner events, emails, and memory. When the data is stale or hard to trust, theatre teams lose time checking, chasing, escalating, substituting, reordering, or delaying cases.

This platform explores one practical question:

```text
Can tomorrow's surgical case proceed from a materials, instruments, and preference-readiness point of view?
```

The target product outcome is a unified Case Readiness view:

```text
CASE_10421
Preference requirements     ready
Internal stock              ready
Loan kit                    at risk
Sterilisation               blocked

READINESS: AT RISK
Reason: loan kit delivered but not released for sterilisation
Owner: loan-kit coordinator
Deadline: 14:00
```

## Current Status

This repository is a production-oriented data product. Local Docker, MinIO, Postgres, pipeline execution, tests, and Streamlit views are the source of truth for what is proven in code. Azure support exists, but each new change only affects Azure after a new image is built, pushed, deployed, and verified against Azure services.

| Area | Status |
| --- | --- |
| Surgeon Preference | Most advanced module. Local medallion pipeline, MinIO/Postgres integration, clinical reference enrichment, Streamlit workflow, Postgres current-card source of truth, version history, rollback, tenant-aware access, and UI-independent application services are implemented with local tests. Tenant isolation and recovery coverage are still incomplete. |
| Stock Inventory | Active module. Local pipeline, synthetic inventory sources, reconciliation foundations, Gold outputs, dashboard foundations, tests, and cloud scaffolding are in place. Azure hardening remains in progress. |
| Loan Kit Management | Next module. Scoped conceptually, not yet implemented as a pipeline. |
| Case Readiness | Target combined product. Not yet built; depends on the three pipelines above. |
| Shared platform | Shared provider-neutral object storage exists for MinIO and Azure Blob. More shared database, contracts, lineage, quality, orchestration, and observability utilities are still planned. |
| Azure | Existing resources are present, but the subscription is disabled and Container Apps compute is suspended. No latest-code deployment or end-to-end Azure verification has been completed. Reactivate the subscription before provisioning, deploying, or running cloud checks. |

## What The Platform Should Prove

The project is strongest when it proves a complete operational slice rather than a huge hospital ecosystem. The intended slice is:

1. Surgeon Preference tells us what a case requires.
2. Stock Inventory tells us what the hospital has, where it is, and whether it is usable.
3. Loan Kit Management tells us what must come from suppliers and whether it is ready.
4. Case Readiness combines those signals into a clear status, reason, owner, and deadline.

The platform should avoid expanding into wider analytics until this slice is defensible with contracts, lineage, idempotency, failure handling, and deployment evidence.

## Pipeline Pattern

Each pipeline follows a medallion-style flow:

```text
Landing
  preserve the original source file
Bronze
  log raw files, raw records, checksums, and ingestion metadata
Silver
  clean, standardise, validate, and enrich records
Gold
  publish operational outputs, analytics outputs, and dashboard-ready data
Product workflow
  show users current state, proposed changes, history, and exceptions
```

For non-technical readers: each stage makes the data more trustworthy while keeping evidence of where it came from and what changed.

## Surgeon Preference

Surgeon Preference automates the preference-card workflow. It starts with messy synthetic source data, passes it through the medallion pipeline, and publishes clinically aligned preference cards for frontline staff.

Current capabilities:

- Generates clinically aligned synthetic preference-card data at 1000-card scale.
- Processes source data through Landing, Bronze, Silver A, Silver B, and Gold.
- Validates procedure-specific instruments, packs, consumables, disposables, equipment, and special instructions.
- Writes files to MinIO locally or Azure Blob through a storage abstraction.
- Writes metadata, audit, workflow, and operational current-card records to Postgres.
- Bootstraps a Postgres-backed Iceberg SQL catalog foundation.
- Serves cards through Streamlit.
- Reads current cards from operational Postgres first, with Gold snapshot fallback.
- Supports draft edits, draft creation, review, controlled publish, version history, rollback, access requests, user roles, and organisation scoping.
- Exports Gold snapshots after operational publishes so object storage remains the evidence and analytics layer.

For implementation details, use the Surgeon Preference links in [Start Here](#start-here), especially the execution plan, module overview, local evidence, DBeaver inspection guide, rollback design, and access model.

## Stock Inventory

Stock Inventory connects theatre demand with stock availability and risk. In simple terms, Surgeon Preference says, "This is what the surgeon expects for the case." Stock Inventory asks, "Do we have it, where is it, and is it usable?"

Current capabilities:

- Generates clinically aligned synthetic stock data.
- Models manual count files, scanner/barcode event files, and ERP-style stock balance files.
- Tracks item catalogue, supplier, location, lot, expiry, recall, sterility, and quantity data.
- Runs Bronze, Silver, and Gold processing locally.
- Publishes readiness, shortage, reorder, risk, usage, cost, surgeon, and procedure outputs.
- Provides dashboard foundations and cloud deployment scaffolding.
- Includes quality gates and tests.

Key hardening still needed:

- Define explicit source-of-truth and reconciliation policy between ERP, scanner events, and manual counts.
- Strengthen temporal modelling: quantity where, when, according to which source.
- Add stronger duplicate-event, late-event, and conflicting-balance handling.
- Complete Azure persistent Blob/Postgres configuration, migrations, managed identities, and deployed dashboard verification.

Substitution wording should stay governed. The platform should identify configured substitution candidates requiring authorised review; it should not imply autonomous clinical/device compatibility decisions.

## Loan Kit Management

Loan Kit Management is the next operational pipeline. It has not started as implementation yet.

A loan kit is supplier-managed equipment brought in for a specific case or list. It may include trays, instruments, trials, implants, components, or procedure-specific consumables. Unlike normal stock, it has a time-critical chain of custody across supplier, goods-in, decontamination, sterilisation, theatre, use, reconciliation, and return.

The MVP should answer:

- Which cases require a loan kit?
- Has the request been sent, accepted, and confirmed?
- What must arrive, by when, and for which case?
- Has the correct kit arrived at the correct site?
- Are trays, instruments, trials, implants, components, and consumables present?
- Is the kit checked, decontaminated, sterile, and released?
- Which case is at risk, why, who owns the action, and when must it be escalated?
- What was used, opened, missing, damaged, returned, disputed, charged, or credited?

Build order:

1. Define contracts and business keys.
2. Generate realistic synthetic booking, supplier, delivery, contents, sterilisation, usage, discrepancy, and return events.
3. Build Landing, Bronze, Silver, and Gold with quality gates.
4. Connect to Surgeon Preference requirements and Stock availability.
5. Publish readiness, exception, action-owner, and return worklists.

## Case Readiness Target

Case Readiness is the product layer that connects all three pipelines.

```text
Upcoming case
    -> required items from Surgeon Preference
    -> internal availability from Stock Inventory
    -> external supply status from Loan Kit Management
    -> readiness decision
    -> reason, owner, deadline, escalation
```

Readiness statuses should be simple:

```text
READY
AT RISK
NOT READY
UNKNOWN
```

Every readiness decision should be traceable back to source files, pipeline runs, contracts, validation results, and operational workflow events.

## Repository Shape

```text
platform/
  modules/
    operational/
      surgeon_preference/
      stock_inventory/
      Loan Kit and Instrument Management/
    intelligence/
    ai_training/
  shared/
    storage/
  core/

deployment/
docs/
tests/
```

Active modules:

- `platform/modules/operational/surgeon_preference`
- `platform/modules/operational/stock_inventory`

Next module:

- `platform/modules/operational/Loan Kit and Instrument Management`

## Local Development

The platform is built locally first, then moved to Azure.

Local development uses:

- synthetic data
- local Python pipelines
- Docker Compose
- MinIO object storage
- Postgres metadata and workflow state
- Streamlit dashboards
- pytest test suites

For Surgeon Preference DBeaver inspection, use:

```text
Host: 127.0.0.1
Port: 5433
Database: surgeon_preference
Username: surgeon_preference_user
Password: value of DB_PASSWORD in the module .env
```

Detailed SQL is in:

```text
platform/modules/operational/surgeon_preference/docs/local_postgres_inspection.md
```

## Azure Direction

Azure is the target cloud learning and deployment path.

Planned/used Azure services:

- Azure Blob Storage for object storage
- Azure Database for PostgreSQL for metadata and operational state
- Azure Container Registry for images
- Azure Container Apps for Streamlit-style apps
- Azure Container App Jobs for batch pipelines
- Azure Data Factory for scheduled or event-driven orchestration
- Azure secrets/environment configuration for credentials
- Microsoft Entra ID or Container Apps authentication for real user identity

Current blocker: the Azure subscription is disabled. Existing resources can be inspected, but deployments and Container Apps execution are unavailable while it remains disabled. Do not claim the newest code is proven in Azure until the subscription is active and fresh evidence exists from the deployed image, Azure Blob, Azure Postgres, logs, and dashboard.

## Evidence Still Needed

To make the repository stronger for review or interview use, capture evidence under a dedicated docs/evidence area:

- architecture screenshots
- successful local pipeline run logs
- successful Azure pipeline run logs
- Streamlit screenshots
- MinIO or Azure Blob object listings
- Postgres table screenshots or query outputs
- failed-run example and recovery notes
- quality-gate outputs
- Gold output samples
- deployment screenshots

The most important question the platform should be able to answer in code is:

```text
A file reaches Bronze successfully. Silver processes part of it and fails.
What happens on rerun, and how do we prove Gold is not duplicated or corrupted?
```

## Roadmap

Immediate priorities:

1. Verify Surgeon Preference locally in Docker, MinIO, Postgres, DBeaver, and Streamlit.
2. Reactivate the Azure subscription, inspect the existing resources, deploy the latest Surgeon Preference image, and capture fresh evidence.
3. Continue hardening Stock Inventory with reconciliation, temporal modelling, and Azure verification.
4. Define cross-pipeline contracts between Surgeon Preference and Stock Inventory.
5. Add pipeline-run tracking, lineage, idempotency, failure handling, quarantine/dead-letter paths, and replay semantics across modules.
6. Build Loan Kit Management MVP.
7. Connect all three pipelines into Case Readiness.
8. Add Infrastructure as Code after the target Azure shape is stable enough to reproduce.

Later priorities:

- case scheduling
- instrument and tray tracking
- theatre utilisation
- turnaround time
- cancellation and delay analysis
- cost per case
- clinical coding support
- AI-ready datasets only after operational governance and data quality are mature

## Security And Data Safety

- Real patient data is not used.
- Real hospital stock data is not used.
- Real staff records are not used.
- Secrets must be supplied through local environment variables or Azure secrets.
- `.env` files must not be committed.
- Generated data is for development, testing, demonstration, and product validation.
- Any move toward real data would require governance, data protection review, access control, clinical safety review, and organisation approval.
- The platform should support authorised review and audit, not autonomous clinical decision-making.

## Author

Joshua Ofori Donkor

- GitHub: **JoshuaOforisurg**
- Portfolio focus: surgical operations, biomedical science, theatre workflow, and healthcare data engineering
