# `setup_treatment`

**Allowed values:** `count_as_downtime`, `exclude_from_availability`
**Default:** `count_as_downtime` (textbook OEE)
**Owner:** Operations leadership (proposes), Finance (approves)

## What it is

Decides how **setup / changeover time** affects Availability:

- `count_as_downtime` (textbook): setup minutes are added to `downtime_hours`.
  Penalizes long setups, rewards SMED-style changeover reduction.
- `exclude_from_availability`: setup minutes are removed from
  `scheduled_hours` instead — i.e., setup is treated as time the line was
  *not expected to be producing*. Availability reflects only run-time
  losses.

## When to adjust it

Switch to `exclude_from_availability` when:
- The product mix forces frequent unavoidable changeovers and operators
  feel availability unfairly penalizes them.
- Leadership wants Availability to track only unplanned losses, with setup
  reported separately.

Stay on `count_as_downtime` when:
- Setup-time reduction is an active improvement initiative.
- Comparing against external OEE benchmarks (which assume setup is downtime).

## What it affects

- **Availability** — changes `scheduled_hours` (when excluded) or
  `downtime_hours` (when counted).
- **OEE** — propagates through Availability.

## Data requirement

Whichever mode is selected, the data-entry layer must distinguish setup
minutes from production-loss minutes. If `setup_minutes` is unavailable in
the source data, the assumption has no effect (defaults to including
setup in downtime by virtue of being lumped into the same bucket).
