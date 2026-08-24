# Preliminary clinical-safety boundary

This is an early hazard-oriented note, not a clinical safety case.

| Hazard | Example cause | Initial control |
|---|---|---|
| False theatre-ready status | Missing checks treated as success | All required checks must be explicitly true |
| Wrong case/kit association | Identifier transcription or interface error | Exact identifiers retained; no fuzzy matching |
| Incorrect event order | Late entry or source clock problem | Sequence exceptions remain visible |
| Failed check hidden | Later successful event overwrites history | Events are immutable; failures remain exceptions |
| Stale status | Source/interface stops updating | Source timestamp and last-event time are exposed |
| Automation dependence | Staff assume dashboard replaces inspection | Product boundary and UI wording must state evidence-only role |
| Loss of access | System or network outage | A future deployment requires a tested downtime process |

Before any operational deployment, the hazard log would need named owners,
severity/likelihood assessment, mitigations, residual risk, verification
evidence, and clinical safety officer review.
