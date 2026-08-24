# Workflow definition

## Canonical stages

| Order | Event | Evidence represented |
|---:|---|---|
| 1 | `request_submitted` | A specialist requirement and required-by time were recorded |
| 2 | `request_approved` | The request passed the applicable local approval |
| 3 | `supplier_confirmed` | A supplier explicitly confirmed supply |
| 4 | `delivery_received` | Custody passed to the receiving organisation |
| 5 | `receipt_check_completed` | Contents, identifiers, condition, and documents were checked |
| 6 | `ssd_handover` | Custody and required-by information passed to SSD |
| 7 | `ssd_released` | SSD explicitly recorded completion/release |
| 8 | `theatre_check_completed` | Packaging, indicators, and contents were explicitly checked |
| 9 | `kit_used` | The kit reached the recorded procedure-use stage |
| 10 | `usage_reconciled` | Used, unused, implanted, wasted, or missing items were reconciled |
| 11 | `return_prepared` | Return contents and condition were recorded |
| 12 | `supplier_collected` | Supplier custody was recorded |
| 13 | `workflow_closed` | Operational closure was recorded |

## Important distinctions

- Delivered is not accepted.
- Accepted is not decontaminated.
- SSD release is not, by itself, theatre readiness.
- Theatre readiness is not proof that a kit was used.
- Used is not reconciled or returned.
- Collected is not financial closure.

The event model intentionally preserves these boundaries so a convenient status
cannot conceal missing evidence.
