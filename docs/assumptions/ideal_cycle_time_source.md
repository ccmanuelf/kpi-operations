# `ideal_cycle_time_source`

**Allowed values:** `engineering_standard`, `demonstrated_best`, `rolling_90_day_average`
**Default:** `engineering_standard`
**Owner:** Industrial engineering (proposes), Finance (approves)

## What it is

Decides which `ideal_cycle_time` value is used as the **performance benchmark**
in the Performance and Efficiency formulas:

- `engineering_standard`: the time set by industrial engineering at product
  release, stored on `Product.ideal_cycle_time`.
- `demonstrated_best`: the fastest cycle time the site has actually achieved
  in production.
- `rolling_90_day_average`: the average actual cycle time over the trailing
  90 days, recomputed daily.

## When to adjust it

Switch to `demonstrated_best` when:
- Engineering standards are stale and the line consistently runs faster.
- The goal is to reward continuous improvement rather than meeting a static
  bar.

Switch to `rolling_90_day_average` when:
- Mix changes frequently and standards-vs-actual drift over time.
- The site is in a learning curve and you want to track *recent capability*
  rather than aspirational targets.

Stay on `engineering_standard` when:
- The product is mature and engineering standards are accurate.
- External benchmarking (vendor / industry) requires textbook performance.

## What it affects

- **Performance** — directly changes the `ideal_cycle_time_hours` input.
- **Efficiency** — `ideal_cycle_time_hours` is part of the formula.
- **OEE** — propagates through Performance.
- **Capacity Requirements** — staffing math uses cycle time.
- **Production Capacity** — throughput math uses cycle time.

## Auditability note

When `rolling_90_day_average` is selected, the assumption record's value
field stores the most recently computed value. Change-log entries are written
each time the average is refreshed so the historical reproducibility
guarantee is preserved.
