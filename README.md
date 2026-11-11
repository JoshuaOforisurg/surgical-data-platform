# Surgical Data Platform

A synthetic-first healthcare operations data product in development. The platform explores how preference-card, stock, and loan-kit data can support operational readiness for theatre teams.

The current product focus is deliberately narrow:

```text
Surgeon Preference -> Stock Inventory -> Loan Kit Management -> Case Readiness
```

The project uses **synthetic data only**. It does not contain real patient data, staff records, theatre lists, hospital stock records, or confidential hospital information.

Live project site: [www.surgeonpreference.com](https://www.surgeonpreference.com)

## Start Here

| Product area | Overview |
| --- | --- |
| Surgeon Preference | [`Module README`](platform/modules/operational/surgeon_preference/surgeons_preference%20README.md) |
| Stock Inventory | [`Module README`](platform/modules/operational/stock_inventory/README.md) |
| Loan Kit Management | [`Module README`](platform/modules/operational/Loan%20Kit%20and%20Instrument%20Management/README.md) |

This README describes the product direction and the implementation currently present in the codebase.

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

This repository is an early-stage data product built and tested locally with synthetic data. Cloud deployment and clinical use have not been validated.

| Area | Status |
| --- | --- |
| Surgeon Preference | Most advanced module. Local medallion pipeline, MinIO/Postgres integration, clinical enrichment, Streamlit workflow, operational card versions, rollback, tenant-aware access, and application services have local test coverage. Broader tenant-isolation and recovery assurance remain incomplete. |
| Stock Inventory | Local pipeline, synthetic inventory sources, Gold outputs, dashboard foundation, tests, and preference-card handoff are present. Reconciliation and temporal modelling need further hardening. |
| Loan Kit Management | A synthetic local pipeline now processes request, supplier, kit, item, and event data into operational worklists and quality outputs. It is not yet integrated with the other products or backed by the platform's operational database and object storage. |
| Case Readiness | Target combined product. No unified case-level worklist currently joins all three modules. |
| Shared platform | A provider-neutral object-storage abstraction supports local MinIO and cloud blob storage. Additional shared contracts, database, lineage, quality, orchestration, and observability capabilities remain to be built. |
| Deployment | Local execution is the verified development path. Hosted deployment and end-to-end cloud operation have not been verified. |

## What The Platform Should Prove

The project is strongest when it proves a complete operational slice rather than a huge hospital ecosystem. The intended slice is:

1. Surgeon Preference tells us what a case requires.
2. Stock Inventory tells us what the hospital has, where it is, and whether it is usable.
3. Loan Kit Management tells us what must come from suppliers and whether it is ready.
4. Case Readiness combines those signals into a clear status, reason, owner, and deadline.

The platform is scoped to proving this operational slice before expanding into a broader hospital information system.

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
- Writes files to MinIO locally through a provider-neutral storage abstraction.
- Writes metadata, audit, workflow, and operational current-card records to Postgres.
- Bootstraps a Postgres-backed Iceberg SQL catalog foundation.
- Serves cards through Streamlit.
- Uses operational Postgres for current cards and versions; object storage holds source and versioned pipeline artifacts.
- Supports draft edits, draft creation, review, controlled publish, version history, rollback, access requests, user roles, and organisation scoping.
- Exports Gold snapshots after operational publishes so object storage remains the evidence and analytics layer.

For implementation details, see the [Surgeon Preference module README](platform/modules/operational/surgeon_preference/surgeons_preference%20README.md).

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

The current module does not yet establish an authoritative reconciliation policy across ERP balances, scanner events, and manual counts, or demonstrate complete handling of late events and conflicting balances. Hosted operation has not been verified.

Substitution wording should stay governed. The platform should identify configured substitution candidates requiring authorised review; it should not imply autonomous clinical/device compatibility decisions.

## Loan Kit Management

Loan Kit Management is an early synthetic operational pipeline. Its current local implementation is a starting point, not a deployed or integrated service.

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

The current implementation does not yet provide the platform's persistent
metadata and storage integration, organisation-scoped access, or a joined
workflow with the other operational modules.

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

Every readiness decision should be traceable back to source files, pipeline runs, contracts, validation results, and operational workflow events. This unified runtime is not implemented yet. The current synthetic case identifiers differ between Stock Inventory and Loan Kit Management, and item mappings are incomplete; a shared tested contract is needed before joining the outputs.

## Repository Shape

```text
platform/
  modules/
    operational/
      surgeon_preference/
      stock_inventory/
      Loan Kit and Instrument Management/
    intelligence/
  shared/
    storage/
  core/

deployment/
tests/
```

Active modules:

- `platform/modules/operational/surgeon_preference`
- `platform/modules/operational/stock_inventory`

Additional operational module:

- `platform/modules/operational/Loan Kit and Instrument Management`

## Local Development

Local development uses:

- synthetic data
- local Python pipelines
- Docker Compose
- MinIO object storage
- Postgres metadata and workflow state
- Streamlit dashboards
- pytest test suites

## Security And Data Safety

- Real patient data is not used.
- Real hospital stock data is not used.
- Real staff records are not used.
- Secrets must be supplied through local environment variables or an approved secret manager.
- `.env` files must not be committed.
- Generated data is for development, testing, demonstration, and product validation.
- Any move toward real data would require governance, data protection review, access control, clinical safety review, and organisation approval.
- The platform should support authorised review and audit, not autonomous clinical decision-making.

## Author

Joshua Ofori Donkor

- GitHub: **JoshuaOforisurg**
- Portfolio focus: surgical operations, biomedical science, theatre workflow, and healthcare data engineering
