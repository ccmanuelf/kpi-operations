"""Response contract for `GET /api/pivot/{dataset}`.

Deliberately envelope-only. The five keys the engine always returns are
declared; the measures inside `rows[]`/`totals` are NOT, because they are
dataset-dependent and a closed model would silently drop them.

`backend/pivot/registry.py::DATASETS` defines six datasets whose measure
sets are disjoint (read 2026-08-30):

    production  units, earned_hours, excluded_entries, run_hours,
                downtime_hours, operators, efficiency_pct
    downtime    downtime_hours, events, share_of_window_pct
    quality     inspected, passed, defective, defects, fpy_pct
    holds       holds, hold_days, avg_days_per_hold
    labor       scheduled, actual, normal, double, triple, unsplit_actual,
                billed, available_for_efficiency, earned_hours,
                excluded_entries, efficiency_available_basis
    delivery    delivered, on_time, justified_late, net_on_time,
                otd_gross_pct, otd_net_pct

A model enumerating any one of those would make Pydantic strip the other
five datasets' measures out of the response -- turning a typed contract
into a data-loss bug. The contract test that pins this is
`test_pivot_envelope_holds_for_every_dataset`, which walks DATASETS itself
rather than the single dataset the capture's `literal` names.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class PivotResponse(BaseModel):
    """`backend/pivot/engine.py` builds exactly these five keys.

    `group_by` is echoed from the query string and is None when the caller
    omits it. `rows` is one dict per bucket (plus group key when grouping);
    `totals` is a single roll-up over the same measures.
    """

    dataset: str
    bucket: str
    group_by: Optional[str] = None
    rows: List[Dict[str, Any]]
    totals: Dict[str, Any]
