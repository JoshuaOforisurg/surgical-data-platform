# Loan Kit and Instrument Management Pipeline

Synthetic-first data product for reconstructing and reviewing the lifecycle of
surgical loan kits, reusable instruments, implants, and consumables.

> **Status:** early technical skeleton. It is not validated, deployed, or
> approved for clinical use. The repository contains synthetic data only.

## Product hypothesis

Loan-kit coordination frequently crosses surgeon requests, theatre teams,
suppliers, procurement, reception, sterile services, operating theatres, and
finance. Evidence can be distributed between email, telephone calls, letters,
paper checklists, supplier documents, and local knowledge.

This pipeline tests whether a shared, auditable event model can answer:

- What was requested, for which case, and by when?
- Has the supplier confirmed availability and delivery?
- Where is the kit and which team owns the next action?
- Were receipt, contents, condition, documentation, SSD, and final packaging
  checks explicitly recorded?
- Is the recorded evidence sufficient to describe the kit as theatre-ready?
- Which implants or consumables were used, unused, wasted, or returned?
- Was the kit collected and can the workflow be financially reconciled?
- Which cases contain missing, late, contradictory, or unsafe evidence?

The pipeline records and evaluates evidence. It does **not** replace physical
checks, sterilisation systems, clinical judgement, supplier instructions, the
patient record, procurement systems, or incident-reporting processes.

## Initial end-to-end slice

```text
synthetic CSV events
        |
        v
contract validation -> workflow reconstruction -> safety/readiness rules
        |                       |                         |
        v                       v                         v
canonical events        kit lifecycle summary        exceptions
                                  |
                                  v
                          pipeline run manifest
```

Workflow evidence is reconstructed across:

```text
request -> approval -> supplier confirmation -> delivery -> receipt checks
-> SSD handover -> SSD release -> theatre checks -> use/reconciliation
-> return -> supplier collection -> closure
```

## Safety boundary

- The software never assumes a kit is sterile because it reached SSD.
- `THEATRE_READY` requires explicit evidence of SSD release, packaging
  integrity, sterility indicator acceptance, contents verification, and no open
  error-severity exceptions.
- Missing data is not converted into a successful check.
- Events retain their source, actor, timestamp, and source event identifier.
- The initial pipeline is descriptive and retrospective. It does not send live
  alerts or authorise clinical use.
- Any future operational deployment would require local governance, information
  governance, user research, downtime procedures, and formal clinical-safety
  work including DCB0129/DCB0160 assessment where applicable.

## Repository structure

```text
config/                 versioned pipeline configuration
contracts/              machine-readable source contracts
data/raw/synthetic/     deliberately fictional source events
docs/                   product, workflow, architecture, and safety notes
src/loan_kit_pipeline/  pipeline package
tests/                  automated behaviour tests
```

## Run locally

Python 3.11 or later is required. The runtime uses only the standard library.

```bash
PYTHONPATH=src python3 -m loan_kit_pipeline \
  --input data/raw/synthetic/loan_kit_events.csv \
  --output data/outputs
```

Expected outputs:

- `canonical_events.csv`
- `kit_lifecycle_summary.csv`
- `exceptions.csv`
- `pipeline_summary.json`
- `run_manifest.json`

Run the tests:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'
```

## Current scope and next increments

Version 0.1 provides the repository skeleton, canonical event contract,
deterministic synthetic demonstration, explicit readiness rules, exception
reporting, lineage fields, reproducible manifest, CLI, and tests.

Not yet implemented:

- database or cloud storage
- user interface, authentication, or role-based approval
- email, EPR, ERP, supplier, SSD, or scanning integrations
- patient-identifiable data
- individual tray/instrument manifest reconciliation
- invoice line reconciliation
- real-time notifications or escalation
- production analytics or clinical deployment

See [the MVP specification](docs/product/mvp.md) and
[workflow definition](docs/product/workflow.md) for the proposed direction.
