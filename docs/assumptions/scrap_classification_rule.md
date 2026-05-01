# `scrap_classification_rule`

**Allowed values:** `rework_counted_as_good`, `rework_counted_as_partial`, `rework_counted_as_bad`
**Default:** `rework_counted_as_good`
**Owner:** Quality leadership (proposes), Finance (approves)

## What it is

Decides how **reworked units** (units that initially failed inspection but
were corrected in-line, without being scrapped) are classified by quality
metrics:

- `rework_counted_as_good`: reworked units are added to the `total_passed`
  numerator. The customer ultimately receives a conforming unit; the rework
  effort is tracked separately via Rework Impact.
- `rework_counted_as_partial`: reworked units are *partially* counted —
  half-credit (0.5 each) — to reflect the labor cost while still
  acknowledging the unit shipped.
- `rework_counted_as_bad`: reworked units are excluded from `total_passed`
  entirely. FPY drops every time rework happens, even if the part is
  ultimately conforming. Strict definition of "first-pass yield".

## When to adjust it

Use `rework_counted_as_bad` when:
- Leadership wants to drive down rework specifically.
- Aligning to a customer/contract definition that excludes rework from FPY.
- The site has high rework volumes and the textbook FPY is misleadingly high.

Use `rework_counted_as_partial` when:
- Both the cost of rework and the customer-facing yield matter.
- A single number is needed that balances strict-FPY and ship-rate.

Stay on `rework_counted_as_good` when:
- The site benchmarks against industry-standard FPY.
- Rework volumes are low enough that the distinction is immaterial.

## What it affects

- **FPY** — changes `total_passed`.
- **Scrap Rate** — `units_scrapped` is unchanged, but the denominator may
  be tightened in derived metrics.
- **Defect Escape Rate** — affects which units are considered "defects" at
  inline stages.
- **Quality Rate** (inline) — `defect_count` and `scrap_count` interpretation.
- **OEE** — propagates through Quality.

## Data requirement

The QualityEntry table must distinguish `units_reworked` from
`units_scrapped`. The current schema does — see `backend/orm/quality_entry.py`.
