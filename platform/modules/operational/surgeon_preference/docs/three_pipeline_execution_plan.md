# Three-Pipeline Execution Plan

## Purpose

This is the build plan for turning the surgical data platform into a credible,
defensible data product. Scope is deliberately frozen at three operational
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

## Frontend Migration Boundary

Streamlit is the current product interface and a useful way to validate the
preference-card workflow. Do not rewrite it just to look more production-like.
Move to a separate web frontend after the preference use cases have stable,
UI-independent application services and the tenant authorization and recovery
checks are proven. Complete that migration before onboarding external
organisations with real operational data; it does not need to wait for Stock
Inventory, Loan Kit Management, or the complete Case Readiness product.

The target boundary is:

```text
Web UI / Streamlit adapter -> application services or API -> domain + repositories
```

Theatre Readiness sits above the three data products and consumes their
versioned, tenant-scoped operational outputs. It should not depend on Streamlit
or force the UI migration. Preference remains the first requirement signal;
inventory and loan-kit signals can be added behind the same product/API boundary.

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
- [x] Replace deployment-configured organisation context with
      database-validated active membership and membership-scoped roles.
- [x] Resolve app permissions from organisation membership records; keep
      routine sign-in limited to updating the global user profile.
- [x] Scope access-request decisions, admin membership updates, and workflow
      metadata queries to the configured organisation.
- [x] Allow a user with multiple active memberships to select a workspace
      from server-loaded active membership records.
- [x] Stop treating identity-provider role claims as application roles; use
      the database registry for authorization and disable protected actions if
      that registry is unavailable.
- [x] Block tenant-owned UI data reads when a validated active membership
      cannot be resolved. Keep only an explicitly enabled synthetic,
      read-only demo public; refuse unscoped Gold fallback for tenant reads.
- [x] Capture and persist provider-qualified identity subject IDs; reject
      conflicting subject-to-account bindings.
- [x] Re-resolve active membership and database roles before protected draft,
      review, publish, rollback, and organisation-admin writes.
- [x] Extract draft submission into a UI-independent application service used
      by Streamlit, with injectable storage/repository dependencies.
- [x] Extract review submission into a UI-independent application service;
      authorize from fresh membership roles and report partial audit failures.
- [x] Extract approved-card publishing into a UI-independent service that
      updates operational Postgres first and reports downstream partial states.
- [x] Extract rollback into a UI-independent service that creates a new
      operational version and reports export/audit partial states.
- [x] Extract preference read/search use cases behind the same
      application-service boundary.
- [x] Define stable request/response contracts for those use cases before
      building a separate frontend or public API.
- [x] Enforce actor membership inside repository transactions for protected
      workflow, card publish/rollback, access-request, and membership-admin
      writes; evaluate PostgreSQL row-level security as defense in depth.
- [ ] Add PostgreSQL row-level security as defense in depth.
- [ ] Decouple membership identity from mutable email and implement an audited
      account-linking/email-change migration.
- [ ] Complete tenant isolation proof across cards, drafts, reviews, publish events,
      access requests, counts, and failure paths with at least two organisations
      against a real two-tenant database fixture.
- [x] Verify local end-to-end run: generate -> landing -> Bronze -> Silver ->
      Gold -> Postgres current cards -> Streamlit.
- [ ] Verify Azure end-to-end run and capture evidence.
- [x] Add DBeaver/Postgres inspection guide for local operational-card checks.

Evidence to capture:

- [ ] Successful local pipeline run.
- [ ] Successful Azure pipeline run.
- [x] Capture local query evidence from `app_workflow.preference_cards` and
      `app_workflow.preference_card_versions`.
- [x] Exercise Streamlit current-card reads with AppTest.
- [x] Exercise draft submission and review decision.
- [x] Exercise publish and rollback; confirm Postgres current-card and version rows.

Local verification was completed on 2026-10-17 against Docker Postgres on
host port 5433 and a source-built MinIO community server on loopback. The
pipeline processed 1,000 input files, quarantined 110 records, published 168
current cards, and matched CSV/JSON Gold with Postgres. Iceberg SQL catalog
bootstrap reported `available`. Streamlit AppTest exercised a draft, approval,
publish, and rollback, creating successive published and rollback versions
while preserving the original card version. Machine-readable evidence is in
[`docs/evidence/phase1-local-pipeline.json`](evidence/phase1-local-pipeline.json)
and [`docs/evidence/phase1-local-workflow.json`](evidence/phase1-local-workflow.json).
AppTest is not a visual browser review. Azure and the Compose MinIO container
were not verified in this run.

Tenant-scoping note: active memberships determine workspace selection and
tenant-facing reads. Protected writes validate and lock the actor's active
membership and required role inside the same Postgres transaction as the
mutation. The disposable two-tenant Postgres test now proves isolated card
reads/history, tenant-scoped draft writes, rejection of cross-tenant writes,
role-gated administration, and role-gated publish/rollback. It does not yet
cover every access-request, count, and failure path. Do not enable real
multi-organisation data until those cases, email-change/account-linking
handling, and Azure validation are complete.

## Phase 2: Harden Surgeon Preference Pipeline

Goal: answer the interview question: "What happens if Silver crashes halfway
through, and how do you prove Gold is still consistent?"

Before starting this phase, the clinical-gate follow-up corrected an overly
broad system matcher that treated shared instrument names as evidence of the
observed system. The gate now checks an explicitly supplied system against the
procedure profile, quarantines explicit incompatible or unresolved systems,
and treats missing/non-positive/non-integer instrument quantities as invalid.
Synthetic instrument quantity anomalies are configurable and default to 2%
per item. Focused regression tests cover the affected procedures and rules.
The earlier 1,000-file evidence report records the pre-fix run; run a fresh
pipeline after retry/idempotency work before capturing updated end-to-end
clinical-gate evidence.

Tasks:

- [x] Define stage-level execution state: landing, Bronze, Silver A, Silver B,
      Gold, operational sync.
- [x] Add stage status and timestamps to pipeline metadata.
- [x] Add records received, processed, rejected, quarantined, and published.
- [x] Detect duplicate source files using checksum and source identity
      (stable landing object key includes checksum and filename).
- [x] Make repeated ingestion of a source file idempotent in the Bronze ledger
      through a stable file key and deterministic record IDs, with a run-to-file
      link that preserves original file provenance across executions.
- [x] Reject a duplicate run ID rather than resetting a prior run's state.
- [x] Ensure Silver artifacts are run-scoped.
- [x] Ensure Gold latest is only updated after all quality and contract checks
      pass.
- [x] Add failed-run records with error messages.
- [x] Add run-scoped quarantine manifests for malformed source files in MinIO,
      register each artifact in Postgres, and mark the source/run-file status
      as quarantined. Malformed files are excluded while valid sibling files
      continue through Bronze; the run manifest and rejected-file count retain
      the quarantine outcome.
- [x] Add replay path for failed inputs using `--replay-run <run_id>`. Replay
      downloads the original landed objects, verifies checksums, creates a new
      run linked to the failed run, and relies on stable Bronze identities to
      avoid duplicate source records.
- [x] Add integration tests for duplicate source and rerun behaviour against
      Postgres and MinIO. The disposable local test runs one clean source twice,
      verifies one Bronze file/record set with links from both runs, confirms
      completed stage metadata, and checks the operational card is not
      re-versioned. It creates and removes a unique test database and bucket.

Failure cases to prove:

- [ ] Malformed JSON.
- [ ] CSV schema change.
- [ ] Invalid date.
- [ ] Missing required surgeon/procedure fields.
- [ ] One bad record in a large batch.
- [ ] Postgres unavailable.
- [ ] Object storage unavailable.
- [ ] Gold publish failure.

The disposable local integration test injects a Silver-B failure, verifies the
failed stage and error are recorded and no Gold latest object is published,
then replays that run and confirms successful publication without duplicating
the Bronze source. A subsequent same-source run remains idempotent. This proves
the Silver-B failure/replay path locally; other failure modes remain open.

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

- [x] Duplicate source file.
- [x] Bronze succeeds, Silver fails.
- [ ] Silver succeeds, Gold fails.
- [ ] Postgres unavailable.
- [ ] Object storage unavailable.
- [ ] One invalid record in a large batch.
- [x] Rerun previous job.
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

Continue closing the Surgeon Preference tenant-authorization gap before
enabling real users or real preference data. Enforce actor membership at the
repository transaction boundary, run the disposable two-tenant test, and
resolve email-change/account-linking behavior. In parallel, move remaining
workflow use cases out of Streamlit so the current UI and a future API can
share the same application layer. Keep the synthetic public demo separate from
tenant data.

In parallel with the pipeline execution plan, continue Phase 2 safe retry and
idempotency for pipeline imports and user publishes. Local verification exposed
a recovery gap: Postgres commits the
current version before Gold snapshots, object events, and draft status are
written. A crash between those steps can leave the operational card updated
while workflow artifacts lag. Add persisted stage state and reconciliation
before retrying a publish or importing the same pipeline output again.

```text
Make tenant authorization membership-based and fail closed for tenant data;
then make retries safe across Postgres and object storage, preserve version
history, and provide a reconciliation path for partially completed publishes.
```

Keep Azure verification scheduled after local retry and recovery behaviour is
demonstrated; this run did not verify an Azure deployment.
