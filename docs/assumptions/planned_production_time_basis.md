# `planned_production_time_basis`

**Allowed values:** `include_scheduled_maintenance`, `exclude_scheduled_maintenance`
**Default:** `include_scheduled_maintenance` (textbook OEE)
**Owner:** Operations leadership (proposes), Finance (approves)

## What it is

Decides whether **scheduled maintenance hours** are part of the
"available time" denominator for Availability and OEE.

- `include_scheduled_maintenance` (textbook): scheduled hours = full shift
  duration. Scheduled maintenance counted as available time that was lost.
  Lower availability number, higher fidelity to "what % of shift produced
  output".
- `exclude_scheduled_maintenance` (preventive-maintenance-friendly):
  scheduled hours = full shift duration **minus** known maintenance windows.
  The denominator shrinks, so a shop that reliably executes its preventive
  maintenance plan gets credit for it.

## When to adjust it

Switch to `exclude_scheduled_maintenance` when:
- The site has a mature preventive-maintenance program tracked separately
  from unplanned downtime.
- Leadership wants Availability to reward consistent execution of planned
  maintenance rather than penalize it.

Stay on `include_scheduled_maintenance` when:
- Scheduled and unplanned downtime are not consistently distinguished in
  data entry.
- The site is benchmarking against external standards (textbook OEE).

## What it affects

- **Availability** — directly changes the `scheduled_hours` input.
- **OEE** — propagates through Availability.
- **Efficiency** — `scheduled_hours` is also an input to the efficiency formula.
- **Capacity Requirements** — `shift_hours` parameter aligns with the basis.

## Example

A 480-minute shift with 60 minutes of scheduled maintenance and 30 minutes of
unplanned downtime:

| Mode | scheduled | downtime | availability |
|---|---|---|---|
| `include_scheduled_maintenance` | 480 | 90 | 81.25% |
| `exclude_scheduled_maintenance` | 420 | 30 | 92.86% |
