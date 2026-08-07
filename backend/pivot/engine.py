"""Generic pivot execution: one SQL aggregate per (day, group), Python bucket
rollup, ratio-of-sums composition, float coercion (Cycle 4 spec §3)."""

from collections import defaultdict
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from typing import Any, Optional, Sequence

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.pivot.buckets import VALID_BUCKETS, bucket_start
from backend.pivot.registry import DATASETS, Component, Count, Dataset, Ratio, Share, Sum


def _as_date(value: Any) -> date:
    # func.date() returns date on MariaDB but str on SQLite
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _as_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def run_pivot(
    db: Session,
    dataset_name: str,
    bucket: str,
    group_by: Optional[str],
    start_date: date,
    end_date: date,
    client_ids: Optional[Sequence[str]],
) -> dict[str, Any]:
    ds = DATASETS[dataset_name]  # KeyError -> route 422
    if bucket not in VALID_BUCKETS:
        raise ValueError(f"bucket must be one of {VALID_BUCKETS}")
    if group_by is not None and group_by not in ds.group_bys:
        raise ValueError(f"group_by must be one of {sorted(ds.group_bys)}")

    components = {n: m for n, m in ds.measures.items() if isinstance(m, (Sum, Count, Component))}

    if ds.fetch is not None:
        day_rows = ds.fetch(db, group_by, start_date, end_date, client_ids)
    else:
        day_rows = _sql_day_rows(db, ds, group_by, start_date, end_date, client_ids, components)

    # rollup: (bucket_start, group_key) -> {component: float}
    acc: dict[tuple, dict[str, float]] = defaultdict(lambda: {n: 0.0 for n in components})
    # Component keys a hook actually emitted at least once, across every row
    # (not per-row) -- distinct from acc's 0.0 default, which is present
    # whether or not the hook ever touched the key. Ratio/Share on a
    # Component that was NEVER produced (e.g. labor's earned_hours when
    # group_by == "labor_class") is omitted rather than shown as 0/None.
    produced: set[str] = set()
    for day, grp, comps in day_rows:
        key = (bucket_start(day, bucket), grp)
        for n in components:
            if n in comps:
                produced.add(n)
            acc[key][n] += _as_float(comps.get(n))

    window_totals = {n: sum(v[n] for v in acc.values()) for n in components}

    rows = []
    for b_start, grp in sorted(acc, key=lambda k: (k[0], str(k[1]))):
        comps = acc[(b_start, grp)]
        row: dict[str, Any] = {"bucket_start": b_start.isoformat(), "group_key": grp}
        row.update(comps)
        row.update(_derived(ds, comps, window_totals, produced))
        rows.append(row)

    totals = dict(window_totals)
    totals.update(_derived(ds, window_totals, window_totals, produced))

    return {
        "dataset": dataset_name,
        "bucket": bucket,
        "group_by": group_by,
        "rows": rows,
        "totals": totals,
    }


def _derived(
    ds: Dataset, comps: dict[str, float], window_totals: dict[str, float], produced: set[str]
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, m in ds.measures.items():
        if isinstance(m, Ratio):
            # A Component-backed side of the ratio that no row ever produced
            # (structurally, not just zero-valued -- e.g. earned_hours for
            # labor's group_by="labor_class") means the ratio never applies
            # to this rollup; omit it entirely rather than 0/None-spamming.
            num_component = isinstance(ds.measures.get(m.numerator), Component)
            den_component = isinstance(ds.measures.get(m.denominator), Component)
            if (num_component and m.numerator not in produced) or (den_component and m.denominator not in produced):
                continue
            den = comps.get(m.denominator, 0.0)
            num = comps.get(m.numerator, 0.0)
            out[name] = round(num / den * m.scale, 2) if den > 0 else None
        elif isinstance(m, Share):
            total = window_totals.get(m.of, 0.0)
            out[name] = round(comps.get(m.of, 0.0) / total * 100, 2) if total > 0 else None
    return out


def _sql_day_rows(
    db: Session,
    ds: Dataset,
    group_by: Optional[str],
    start_date: date,
    end_date: date,
    client_ids: Optional[Sequence[str]],
    components: dict[str, Any],
) -> Iterator[tuple[date, Optional[str], dict[str, Any]]]:
    day_expr = func.date(ds.date_column).label("pivot_day")
    cols = [day_expr]
    gb = ds.group_bys[group_by] if group_by else None
    if gb is not None:
        cols.append(gb.expr.label("pivot_grp"))
    names = list(components)
    for n in names:
        m = components[n]
        cols.append(func.count().label(n) if isinstance(m, Count) else func.sum(m.expr).label(n))

    q = db.query(*cols)
    for target, onclause in ds.joins + (gb.joins if gb else ()):
        q = q.outerjoin(target, onclause)
    q = q.filter(func.date(ds.date_column) >= start_date, func.date(ds.date_column) <= end_date)
    for f in ds.base_filters:
        q = q.filter(f)
    if client_ids is not None:
        q = q.filter(ds.client_column.in_(client_ids))
    q = q.group_by(day_expr, *([gb.expr] if gb else []))

    for row in q.all():
        day = _as_date(row[0])
        grp = str(row[1]) if gb is not None and row[1] is not None else (None if gb is None else "unknown")
        comps = {n: row._mapping[n] for n in names}
        yield (day, grp, comps)
