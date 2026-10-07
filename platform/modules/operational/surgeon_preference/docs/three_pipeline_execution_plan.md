# Three-Pipeline Execution Plan

## Purpose

This is the build plan for turning the surgical data platform into a credible,
defensible portfolio product. Scope is deliberately frozen at three operational
pipelines:

1. Surgeon Preference
2. Stock Inventory
3. Loan Kit Management

The final product layer is Case Readiness: a single operational view that tells
frontline theatre teams whether tomorrow's case is ready, at risk, or not ready
from a preference, stock, and loan-kit perspective.

Do not add case scheduling, robotics, AI, utilisation, staffing, or wider
theatre analytics until this vertical slice is excellent.

## Product Story

The strongest story is:

```text
Surgeon Preference -> Stock Inventory -> Loan Kit Management -> Case Readiness
```

- Surgeon Preference tells us what the surgeon and procedure require.
- Stock Inventory tells us what is internally available.
- Loan Kit Management tells us what must arrive from external suppliers.
- Case Readiness combines those signals into an operational decision.

Example target Gold output:

```text
Case: CASE_10421

Preference requirements:  PASS
Internal stock:           PASS
Implant availability:     PASS
Loan kit:                 AT RISK
Sterilisation:            FAIL

Readiness: AT RISK
Reason: Loan kit delivered but not released for sterilisation.
Owner: Loan Kit Coordinator
Deadline: 14:00
```

## Guiding Rules

- Prove one bounded problem deeply before expanding the platform.
- Prefer evidence over claims.
- Every pipeline output must be traceable to source input.
- Every rerun must be safe.
- Bad records should be quarantined, not allowed to corrupt Gold.
- Object storage is the artifact/evidence layer.
- Postgres is the operational metadata and product-state layer.
- Clinical/device substitution language must stay governed and review-based,
  not autonomous.

## Phase 1: Finish Surgeon Preference V2

Goal: make Surgeon Preference credible as an operational product, not just a
pipeline demo.

Tasks:

- [x] Finish syncing Gold operational cards into Postgres current-card tables.
- [x] Add Streamlit current-card read path: operational Postgres first, Gold
      snapshot fallback.
- [x] Use Postgres as the operational source of truth for current cards.
- [x] Keep Gold CSV/JSON as versioned exports and analytics snapshots.
- [x] Complete draft -> review -> publish against operational Postgres state.
- [x] Add card history view from `preference_card_versions`.
- [x] Add rollback/revert design for published card versions.
- [x] Implement rollback/revert workflow for published card versions.
- [x] Confirm organisation and role scoping across cards, drafts, reviews, and
      publish events.
- [x] Add tests for tenant isolation.
- [ ] Verify local end-to-end run: generate -> landing -> Bronze -> Silver ->
      Gold -> Postgres current cards -> Streamlit.
- [ ] Verify Azure end-to-end run and capture evidence.
- [x] Add DBeaver/Postgres inspection guide for local operational-card checks.

Evidence to capture:

- [ ] Successful local pipeline run.
- [ ] Successful Azure pipeline run.
- [ ] Screenshots or query output from `app_workflow.preference_cards` and
      `app_workflow.preference_card_versions`.
- [ ] Streamlit current-card view.
- [ ] Draft submission.
- [ ] Review decision.
- [ ] Publish event.
- [ ] Postgres current-card and version rows.

## Phase 2: Harden Surgeon Preference Pipeline

Goal: answer the interview question: "What happens if Silver crashes halfway
through, and how do you prove Gold is still consistent?"

Tasks:

- [ ] Define stage-level execution state: landing, Bronze, Silver A, Silver B,
      Gold, operational sync.
- [ ] Add stage status and timestamps to pipeline metadata.
- [ ] Add records received, processed, rejected, quarantined, and published.
- [ ] Detect duplicate source files using checksum and source identity.
- [ ] Make reruns safe for the same source file and run request.
- [ ] Ensure Silver artifacts are run-scoped.
- [ ] Ensure Gold latest is only updated after all quality and contract checks
      pass.
- [ ] Add failed-run records with error messages.
- [ ] Add quarantine records/files for malformed source data.
- [ ] Add replay path for quarantined or failed inputs.
- [ ] Add integration tests for duplicate source and rerun behaviour.

Failure cases to prove:

- [ ] Malformed JSON.
- [ ] CSV schema change.
- [ ] Invalid date.
- [ ] Missing required surgeon/procedure fields.
- [ ] One bad record in a large batch.
- [ ] Postgres unavailable.
- [ ] Object storage unavailable.
- [ ] Gold publish failure.

## Phase 3: Add Observability

Goal: make daily pipeline health visible without reading raw logs.

Tasks:

- [ ] Add or extend `pipeline_runs` with run summary fields.
- [ ] Add stage-level run table if needed.
- [ ] Add structured logs with run ID, stage, record counts, and error type.
- [ ] Add freshness checks for Gold/current-card data.
- [ ] Add product-readiness signals for stale data, failed runs, and incomplete
      cards.
- [ ] Show latest pipeline health in Streamlit admin/metadata area.

Minimum run metadata:

```text
run_id
pipeline_name
stage
started_at
completed_at
status
source_files
records_received
records_processed
records_rejected
records_quarantined
records_published
quality_status
contract_status
error_count
error_message
pipeline_version
schema_version
data_product_version
```

## Phase 4: Add Evidence Documentation

Goal: make the repository prove its claims.

Tasks:

- [ ] Create `docs/evidence/`.
- [ ] Add architecture screenshots/diagrams.
- [ ] Add successful local pipeline evidence.
- [ ] Add successful Azure pipeline evidence.
- [ ] Add failed-run evidence.
- [ ] Add quarantine/replay evidence.
- [ ] Add database schema screenshots or generated schema docs.
- [ ] Add sample Gold outputs.
- [ ] Add Streamlit dashboard screenshots.
- [ ] Add a short demo script showing how to reproduce the local run.

## Phase 5: Stabilise Stock Inventory

Goal: make Stock Inventory a second strong operational pipeline, not just a
side module.

Tasks:

- [ ] Verify current Stock Inventory code and architecture.
- [ ] Define stock domain contracts.
- [ ] Confirm source types: ERP balance, scanner event, manual count.
- [ ] Add persistent object storage and Postgres metadata.
- [ ] Add local end-to-end pipeline run.
- [ ] Add Azure deployment path.
- [ ] Add Gold stock availability output.
- [ ] Add dashboard/worklist for inventory readiness.
- [ ] Add tests for duplicate events and conflicting counts.

## Phase 6: Define Stock Reconciliation Policy

Goal: make inventory quantities explainable.

Questions to answer:

- Which source is authoritative?
- How do scanner events affect ERP balances?
- When does a manual count override system balances?
- How are late-arriving events handled?
- How are duplicate scanner events detected?
- How is a reconciliation decision recorded?

Tasks:

- [ ] Define source priority rules.
- [ ] Add reconciliation status and reason fields.
- [ ] Store source values separately before deriving the reconciled value.
- [ ] Add tests for ERP vs scanner vs manual conflicts.
- [ ] Add Gold output that includes both quantity and explanation.

## Phase 7: Define Shared Cross-Pipeline Contracts

Goal: make the three pipelines joinable and defensible.

Tasks:

- [ ] Define shared business keys:
      case ID, procedure ID, surgeon ID, item ID, supplier ID, kit ID.
- [ ] Define Surgeon Preference required-item contract.
- [ ] Define Stock available-item contract.
- [ ] Define Loan Kit expected-item contract.
- [ ] Define Case Readiness input contract.
- [ ] Add schema versions and compatibility rules.
- [ ] Add contract tests across pipeline boundaries.

## Phase 8: Fix Substitution Governance

Goal: avoid unsafe language and unsafe implied autonomy.

Required language:

- Use "substitution candidate", not "safe substitute".
- Use "requires authorised review" when clinical/device compatibility matters.

Tasks:

- [ ] Rename unsafe fields and README language.
- [ ] Add substitution candidate model:
      candidate item, requested item, rule source, compatibility status,
      review requirement, approval status.
- [ ] Add approval/rejection audit.
- [ ] Ensure no product surface claims autonomous clinical substitution.

## Phase 9: Make Synthetic Data Adversarial

Goal: stop the synthetic generator from making the pipeline too easy.

Add datasets with:

- [ ] Malformed files.
- [ ] Wrong encodings.
- [ ] Renamed columns.
- [ ] Missing columns.
- [ ] Duplicate identifiers.
- [ ] Unknown items.
- [ ] Missing foreign references.
- [ ] Invalid dates.
- [ ] Impossible dates.
- [ ] Unexpected enum values.
- [ ] Conflicting stock quantities.
- [ ] Duplicate scanner events.
- [ ] Late-arriving stock events.
- [ ] Partial supplier/loan-kit events.

Each adversarial dataset should have an expected outcome:

- accepted
- corrected
- quarantined
- rejected
- replayable

## Phase 10: Add Failure And Recovery Integration Tests

Goal: prove reruns do not duplicate or corrupt Gold.

Tests:

- [ ] Duplicate source file.
- [ ] Bronze succeeds, Silver fails.
- [ ] Silver succeeds, Gold fails.
- [ ] Postgres unavailable.
- [ ] Object storage unavailable.
- [ ] One invalid record in a large batch.
- [ ] Rerun previous job.
- [ ] Replay quarantined input.
- [ ] Verify Gold latest remains last-known-good after failed run.

## Phase 11: Extract Shared Platform Capabilities

Goal: avoid duplicating infrastructure across the three pipelines.

Extract shared utilities for:

- [ ] object storage
- [ ] Postgres/database access
- [ ] settings/config
- [ ] structured logging
- [ ] contracts
- [ ] quality gates
- [ ] lineage
- [ ] run tracking
- [ ] quarantine handling
- [ ] orchestration helpers

Domain modules should keep domain logic. Shared infrastructure should move into
shared platform code.

## Phase 12: Add Infrastructure As Code

Goal: make Azure deployment reproducible.

Use Terraform or Bicep for:

- [ ] Resource group.
- [ ] Storage account/container.
- [ ] PostgreSQL.
- [ ] Azure Container Registry.
- [ ] Container App.
- [ ] Container App Job.
- [ ] Managed identities.
- [ ] Permissions/RBAC.
- [ ] Environment variables and secrets.
- [ ] Azure Data Factory or scheduled trigger if retained.

Evidence:

- [ ] Fresh environment can be deployed from IaC.
- [ ] App and job can run using managed identity/secrets.
- [ ] README links to deployment guide.

## Phase 13: Build Loan Kit Management

Goal: build the third pipeline only after Surgeon Preference and Stock are
hardened.

Tasks:

- [ ] Define domain model and contracts first.
- [ ] Generate synthetic supplier and loan-kit events.
- [ ] Landing.
- [ ] Bronze.
- [ ] Silver.
- [ ] Gold.
- [ ] Quality gates.
- [ ] Lineage.
- [ ] Failure handling.
- [ ] Dashboard/worklist.
- [ ] Tests for late supplier updates and incomplete kits.

## Phase 14: Connect The Three Pipelines

Goal: produce a unified operational readiness dataset.

Inputs:

- Surgeon Preference required items.
- Stock internally available items.
- Loan Kit externally supplied items.

Tasks:

- [ ] Join preference requirements to stock availability.
- [ ] Join external requirements to loan-kit status.
- [ ] Calculate missing requirements.
- [ ] Assign owner/action.
- [ ] Produce Case Readiness Gold output.
- [ ] Expose Case Readiness dashboard.

## Phase 15: Build Case Readiness Product

Target statuses:

- `READY`
- `AT_RISK`
- `NOT_READY`

Each readiness row should include:

- [ ] case ID
- [ ] procedure
- [ ] surgeon
- [ ] readiness status
- [ ] missing requirement
- [ ] reason
- [ ] responsible owner
- [ ] required action
- [ ] deadline
- [ ] escalation status
- [ ] source evidence

## Phase 16: Clean Documentation

Goal: make the repository easy to review.

Tasks:

- [ ] Shorten the README to a clear front door.
- [ ] Move detail into dedicated docs:
      architecture, data model, pipelines, deployment, quality, clinical
      governance, runbook, roadmap, evidence.
- [ ] Add a "How to review this repo" section.
- [ ] Add a "How to run locally" section.
- [ ] Add a "What is proved vs planned" section.
- [ ] Remove broad future claims until there is evidence.

## Current Immediate Next Step

Start with Phase 1:

```text
Sync Gold operational preference cards into Postgres current-card tables,
then move the Streamlit current-card read path gradually from Gold CSV toward
operational Postgres.
```

That is the first durable step toward making Surgeon Preference V2 the
transactional product source of truth.
