# G2 Smoke Test Audit - R20261104_0653-1-audit-g2-smoke

## Overview
This audit verifies the data integrity, cost compliance, and failure behavior of the 6 cells identified in ticket R20261104_0653-1-audit-g2-smoke.

## Cells to Audit
| Draft | Status | Arm | Cell ID (Partial) |
|---|---|---|---|
| `dab055` | FAIL | Generic | `1c61bd67...` |
| `dab427` | FAIL | Generic | `c371af2b...` |
| `dab427` | PASS | Localized | `e69544e7...` |

## Audit Criteria
- **Initial vs. Final States**: Verify that the state transitions are correct for both passing and failing cells.
- **Regressions**: Ensure no regressions occur (expected 0).
- **Zero Consumption**: PASS cells must have zero consumption of resources beyond what is necessary for completion.
- **Failure Behavior**: Failed cells must trigger `consecutive_no_progress` correctly.
- **Cost Analysis**: Calculate average calls, input tokens, and output tokens for generic vs. localized arms.

## Audit Results
*(To be filled)*
