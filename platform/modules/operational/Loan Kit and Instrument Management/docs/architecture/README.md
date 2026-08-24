# Architecture

The initial architecture is a deterministic local batch pipeline:

```text
CSV source -> strict parsing -> canonical events -> grouped lifecycles
           -> workflow/readiness rules -> summaries + exceptions + manifest
```

The domain logic is independent of storage and UI concerns so future adapters
can receive records from scanning systems, SSD, procurement, or suppliers
without changing the canonical lifecycle rules.

## Design decisions

- Standard-library runtime keeps the first proof easy to inspect and run.
- Immutable event records preserve historical evidence.
- Derived lifecycle summaries are rebuildable and are not source truth.
- Rules emit exceptions rather than mutating or inventing source data.
- Output ordering and hashes are deterministic for reproducible review.
