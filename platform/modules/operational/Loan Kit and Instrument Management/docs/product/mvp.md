# Minimum viable product specification

## Objective

Prove that event evidence from a loan-kit workflow can be standardised,
reconstructed, checked, and made auditable without replacing authoritative
clinical or business systems.

## Initial users

- instrument/loan-kit coordinator
- theatre reception practitioner
- sterile services team
- theatre practitioner or team leader
- procurement/finance reviewer
- medical device or clinical governance reviewer

Supplier access is deliberately deferred until internal ownership, information
sharing, and workflow rules have been validated.

## MVP capabilities

1. Accept versioned synthetic workflow-event data.
2. Reject malformed records without silently repairing them.
3. Preserve source identifiers, timestamps, actors, and source systems.
4. Reconstruct one chronological lifecycle per kit request.
5. report missing mandatory stages and sequencing problems.
6. Evaluate readiness only from explicit check evidence.
7. Report lead time, current recorded status, exceptions, and closure.
8. Produce deterministic CSV/JSON evidence for review and testing.

## Out of scope

- clinical decisions or permission to use a device
- replacement of SSD tracking or steriliser release records
- automated supplier selection or purchasing
- live patient data
- invoice payment approval
- RFID hardware
- predictive models

## Proposed success measures for a future pilot

- percentage of kits ready by the locally agreed deadline
- request-to-confirmation and receipt-to-SSD durations
- first-delivery completeness and documentation failure rates
- staff time and number of chases per request
- loan-kit-related delays or cancellations
- return discrepancies and collection delays
- invoice discrepancies
- time required to identify affected kits/cases during a simulated recall

Thresholds must be agreed before a live pilot; this repository does not invent
clinical or operational targets.
