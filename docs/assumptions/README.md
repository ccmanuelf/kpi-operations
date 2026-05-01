# Calculation Assumptions Catalog

This directory holds the rationale for each named assumption in the v1 catalog
(see `backend/services/calculations/assumption_catalog.py`).

Per the dual-view architecture spec, every named assumption requires a markdown
document explaining **what it is, when to adjust it, and what it affects**.
Adding a new assumption requires (a) approval by the spec owner, (b) a new
catalog entry, (c) a new doc in this directory, and (d) corresponding rows in
the `METRIC_ASSUMPTION_DEPENDENCY` table.

The total catalog is capped at **15 entries** in v1. Six are currently active
(see below); nine slots are reserved for future approved additions.

## v1 catalog

| Name | Default | Affects |
|---|---|---|
| [`planned_production_time_basis`](./planned_production_time_basis.md) | `include_scheduled_maintenance` | Availability, OEE, Efficiency, Capacity Requirements |
| [`ideal_cycle_time_source`](./ideal_cycle_time_source.md) | `engineering_standard` | Performance, Efficiency, OEE, Capacity Requirements, Production Capacity |
| [`setup_treatment`](./setup_treatment.md) | `count_as_downtime` | Availability, OEE |
| [`scrap_classification_rule`](./scrap_classification_rule.md) | `rework_counted_as_good` | FPY, Scrap Rate, Defect Escape Rate, Quality Rate, OEE |
| [`otd_carrier_buffer_pct`](./otd_carrier_buffer_pct.md) | _no buffer_ (0%) | OTD |
| [`yield_baseline_source`](./yield_baseline_source.md) | `theoretical` | Quality Score |

## Deferred to a future revision

Two assumptions named in the spec are deferred until the corresponding metrics
exist in the system:

- `wip_valuation_method` — requires inventory valuation logic (FIFO/weighted
  average/standard cost). No inventory metric currently exists.
- `indirect_labor_allocation_rule` — requires labor cost metrics. None exist
  yet.
