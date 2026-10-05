# Surgeon Preference Productisation Roadmap

## Product Goal

The product should replace theatre preference-card paper folders and manually
edited computer archives with a controlled digital workflow:

1. Theatre staff search and view the current approved preference card.
2. Staff submit proposed changes when surgeon preferences change.
3. A reviewer/admin checks the draft for clinical and operational safety.
4. Approved changes are published into the current preference-card record.
5. The pipeline refreshes, validates, audits, versions, and exposes the latest
   approved cards every day.

The frontline user should experience this as a simple operational tool, not as
a data pipeline. The data engineering layer remains the trust, lineage,
validation, audit, and analytics foundation underneath the product.

## What Already Exists

- MinIO/Azure Blob object-storage abstraction for landing, Bronze, Silver, and
  Gold artifacts.
- Postgres metadata catalogue for pipeline runs, landed files, object-store
  objects, Gold artifacts, workflow users, access requests, draft reviews, and
  audit events.
- Clinically aligned synthetic data generation at scale.
- Silver clinical enrichment and validation.
- Silver-to-Gold boundary contract validation.
- Quality gate before Gold publication.
- Versioned Gold outputs plus latest operational Gold view.
- Streamlit app for viewing current cards, submitting drafts, reviewing drafts,
  publishing approved drafts, managing access, and inspecting metadata.
- Role-aware access model for editor, reviewer, and admin workflows.
- Product readiness checks for Gold completeness, draft backlog, pipeline
  metadata, and contract evidence.

## Main Holes

### 1. The Current Card Source Of Truth Is Still A File

The current approved preference cards are read from a Gold CSV/object. That is
good for pipeline output, but it is not ideal for an interactive product where
users edit, review, publish, roll back, and expect strong consistency.

Target:

- Postgres should hold the operational current state:
  - `preference_cards`
  - `preference_card_versions`
  - `preference_card_items`
  - `preference_card_drafts`
  - `preference_card_reviews`
  - `preference_card_publish_events`
- Object storage should remain the artifact lake for raw files, pipeline
  outputs, snapshots, analytics exports, and evidence bundles.

### 2. The App Is Doing Too Much Directly

Streamlit currently talks directly to object storage and Postgres-style service
functions. This is acceptable for a prototype, but a real product needs a
backend boundary.

Target:

- Add a backend API layer, likely FastAPI first.
- Streamlit or a future web frontend calls the API.
- The API owns validation, transactions, permissions, audit, publishing, and
  integration with the pipeline.

### 3. Clinical Safety Needs Explicit Workflow Rules

The pipeline validates clinical alignment, but the product needs safety rules
around edits:

- Consumables must align to the procedure family.
- Instrument sets must align to the procedure family.
- Critical instructions should be procedure-specific.
- Certain fields should require reviewer sign-off before publishing.
- High-risk changes should be flagged separately, for example implants,
  laterality, positioning, tourniquet use, antibiotic cement, radiology, or
  specialist equipment.

### 4. Multi-Hospital Use Needs Proper Tenancy

The current organisation model is a good start, but worldwide users require
strong tenant isolation:

- every card, draft, publish event, user, and audit row must be scoped by
  organisation/workspace
- object keys should include organisation/workspace prefixes
- admins must not see other organisations by accident
- tests should prove cross-tenant isolation

### 5. Daily Refresh Needs To Be Product-Led

The pipeline can run on schedule, but the real business event is not only
"process files daily". It is:

- detect approved preference-card changes
- publish them safely
- create daily snapshots
- generate an audit report
- alert if pipeline, contract, or quality checks fail
- keep last known good Gold/current state available if a new run fails

## Target Architecture

```text
Frontend
  Streamlit now; React/Next.js later if needed
        |
        v
Product API
  authentication context
  RBAC/tenant checks
  draft/edit/review/publish transactions
  clinical edit rules
  audit events
        |
        +--------------------+
        |                    |
        v                    v
Operational Postgres       Object Storage
  current cards              raw uploads
  versions                   Bronze/Silver/Gold artifacts
  drafts                     manifests
  reviews                    analytics snapshots
  audit
        |
        v
Pipeline Orchestration
  scheduled daily refresh
  manual/admin trigger
  clinical enrichment
  contract checks
  quality gates
        |
        v
Analytics Layer
  cost analysis
  stock readiness
  loan kit readiness
  variation reporting
```

## Why Data Engineering Still Matters

This is full-stack product development now, but the core defensibility is data
engineering:

- lineage: knowing exactly where each preference came from
- quality: stopping clinically unsafe or incomplete records from becoming
  current
- reproducibility: rebuilding Gold/current state from source and versioned
  decisions
- auditability: proving who changed what, when, why, and what was published
- scalability: handling many hospitals, specialties, procedures, and future
  analytics pipelines
- interoperability: later mapping procedure, stock, theatre, and possibly FHIR
  data into a shared model

The product should be easy enough for theatre staff, but engineered like a
regulated operational data platform.

## Build Phases

### Phase 1: Stabilise The Current Product

- Keep Streamlit as the frontend.
- Add operational Postgres tables for current cards, versions, drafts, and
  publish events.
- Make Gold CSV an export/snapshot, not the only source of current state.
- Add tests for edit, review, publish, rollback, and tenant isolation.
- Add a daily product-readiness page for admins.

### Phase 2: Add Backend API

- Introduce FastAPI beside the Streamlit app.
- Move permissions, draft submission, review, publish, and audit writes into
  API services.
- Keep Streamlit as a thin client calling the API.
- Add API tests and OpenAPI documentation.

### Phase 3: Real Pilot Readiness

- Enable Azure authentication in production.
- Lock down public editing.
- Add organisation onboarding.
- Add backup/restore checks.
- Add monitoring and alerting.
- Add a clear "no patient-identifiable data" boundary until governance is
  ready.

### Phase 4: Frontline Workflow Depth

- Add fast search by surgeon, specialty, procedure, theatre, and equipment.
- Add print-ready views for theatres that still need paper.
- Add change history per card.
- Add risk flags for clinically significant changes.
- Add procedure-specific edit suggestions.

### Phase 5: Platform Expansion

- Connect stock inventory.
- Connect loan kits.
- Add readiness checks: missing instruments, low stock, loan kit not arrived,
  expired consumables, high-cost variation.
- Build analytics once operational trust is strong.

## Immediate Next Implementation

The next code step should be to introduce the operational Postgres card model
while keeping the existing object-storage Gold outputs. This gives the product
a proper transactional heart without throwing away the medallion pipeline.

Suggested first tables:

- `app_workflow.preference_cards`
- `app_workflow.preference_card_versions`
- `app_workflow.preference_card_drafts`
- `app_workflow.preference_card_publish_events`

Suggested first service:

- `streamlit_services/preference_card_repository.py`

The service should support:

- load current cards for an organisation
- import latest Gold into operational tables
- create draft
- approve/reject draft
- publish draft as a new version
- return card history
- export current state back to Gold-compatible CSV
