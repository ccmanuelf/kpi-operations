"""
v1 catalog of named calculation assumptions.

Per the dual-view architecture spec § Phase 2, total `assumption_name` values
must remain ≤ 15 across the system in v1. Each new assumption requires explicit
spec-owner approval and a markdown rationale doc in `/docs/assumptions/`.

This catalog is the authoritative allow-list: the service layer rejects any
assumption_name not registered here. Adding a new assumption is a two-step
process:
  1. Add the entry below (with valid-value schema and a one-line description)
  2. Add a row to METRIC_ASSUMPTION_DEPENDENCY for each metric it affects

Storage format: assumption values are JSON-encoded in the DB. The
`allowed_values` list (when present) constrains permitted values; absent
means any JSON-serialisable value is allowed.
"""

from typing import Any


# Each entry: (name, description, allowed_values | None, default_value)
# - allowed_values=None means free-form (must still be JSON-serialisable).
# - default_value is the textbook baseline used by Phase 5 variance reporting
#   to compute "deviation from default" per site.
V1_CATALOG: dict[str, dict[str, Any]] = {
    "planned_production_time_basis": {
        "description": "Does scheduled maintenance count as available time?",
        "allowed_values": ["include_scheduled_maintenance", "exclude_scheduled_maintenance"],
        "default_value": "include_scheduled_maintenance",
    },
    "ideal_cycle_time_source": {
        "description": "Where the ideal cycle time used for performance/efficiency comes from.",
        "allowed_values": ["engineering_standard", "demonstrated_best", "rolling_90_day_average"],
        "default_value": "engineering_standard",
    },
    "setup_treatment": {
        "description": "How setup time is counted for availability.",
        "allowed_values": ["count_as_downtime", "exclude_from_availability"],
        "default_value": "count_as_downtime",
    },
    "scrap_classification_rule": {
        "description": "Whether reworked units count as good, partial, or bad.",
        "allowed_values": ["rework_counted_as_good", "rework_counted_as_partial", "rework_counted_as_bad"],
        "default_value": "rework_counted_as_good",
    },
    "otd_carrier_buffer_pct": {
        "description": "Percentage buffer added to the planned delivery date for OTD evaluation.",
        # Free-form numeric: validated as 0 <= n <= 100 in the service layer.
        "allowed_values": None,
        "default_value": 0,
    },
    "yield_baseline_source": {
        "description": "Reference baseline against which yield is judged.",
        "allowed_values": ["theoretical", "demonstrated", "contractual"],
        "default_value": "theoretical",
    },
}


KNOWN_ASSUMPTION_NAMES: frozenset[str] = frozenset(V1_CATALOG.keys())

# Spec § Configuration scope: hard cap at 15 in v1.
MAX_CATALOG_SIZE = 15

assert len(V1_CATALOG) <= MAX_CATALOG_SIZE, (
    f"Assumption catalog exceeds v1 cap of {MAX_CATALOG_SIZE}. "
    f"Each new entry requires spec-owner approval — do not bypass."
)


# Canonical metric → assumption dependency map. Engineering-curated; this is
# the source of truth used to seed METRIC_ASSUMPTION_DEPENDENCY at deploy time
# (call `seed_metric_dependencies(db)` below). The Phase 4 inspector UI reads
# from the DB table, not from this constant, so site-specific overrides remain
# possible if a deployment needs them.
CANONICAL_METRIC_DEPENDENCIES: list[tuple[str, str, str]] = [
    # (metric_name, assumption_name, usage_notes)
    ("oee", "setup_treatment", "Affects availability component."),
    ("oee", "planned_production_time_basis", "Affects availability denominator."),
    ("oee", "ideal_cycle_time_source", "Affects performance component."),
    ("oee", "scrap_classification_rule", "Affects quality component."),
    ("availability", "setup_treatment", "Whether setup time counts as downtime."),
    ("availability", "planned_production_time_basis", "Scheduled-maintenance treatment."),
    ("performance", "ideal_cycle_time_source", "Source of ideal_cycle_time used in formula."),
    ("efficiency", "ideal_cycle_time_source", "Source of ideal_cycle_time used in formula."),
    ("efficiency", "planned_production_time_basis", "Scheduled-hours basis."),
    ("fpy", "scrap_classification_rule", "Whether reworked units count as first-pass good."),
    ("scrap_rate", "scrap_classification_rule", "Definition of scrap vs rework."),
    ("defect_escape_rate", "scrap_classification_rule", "Definition of escape vs rework."),
    ("quality_rate", "scrap_classification_rule", "Treatment of reworked units in inline quality."),
    ("quality_score", "yield_baseline_source", "Reference baseline for grade interpretation."),
    ("otd", "otd_carrier_buffer_pct", "Site-configured buffer added to planned delivery date."),
    ("capacity_requirements", "ideal_cycle_time_source", "Source of cycle_time in staffing math."),
    ("capacity_requirements", "planned_production_time_basis", "Scheduled-hours basis."),
    ("production_capacity", "ideal_cycle_time_source", "Source of cycle_time in throughput math."),
]


def seed_metric_dependencies(db) -> int:
    """
    Idempotently insert CANONICAL_METRIC_DEPENDENCIES into the
    METRIC_ASSUMPTION_DEPENDENCY table.

    Returns the number of rows newly inserted (existing rows are preserved).
    Safe to call at deploy time, in tests, or from a one-shot script.
    """

    from backend.orm.calculation_assumption import MetricAssumptionDependency

    inserted = 0
    for metric_name, assumption_name, notes in CANONICAL_METRIC_DEPENDENCIES:
        exists = (
            db.query(MetricAssumptionDependency)
            .filter(
                MetricAssumptionDependency.metric_name == metric_name,
                MetricAssumptionDependency.assumption_name == assumption_name,
            )
            .first()
        )
        if exists is not None:
            continue
        db.add(
            MetricAssumptionDependency(
                metric_name=metric_name,
                assumption_name=assumption_name,
                usage_notes=notes,
            )
        )
        inserted += 1

    if inserted:
        db.commit()
    return inserted


def is_known(assumption_name: str) -> bool:
    return assumption_name in KNOWN_ASSUMPTION_NAMES


def get_default_value(assumption_name: str) -> Any:
    """Return the textbook default value for an assumption, or None if unknown."""

    entry = V1_CATALOG.get(assumption_name)
    return entry["default_value"] if entry else None


def deviation_magnitude(assumption_name: str, value: Any) -> float:
    """
    Compute a comparable deviation score for sorting in the variance report.

    Categorical assumptions: 0.0 if value matches default, else 1.0.
    `otd_carrier_buffer_pct` (numeric): the actual buffer percent — already
    a meaningful magnitude, returned as a float.

    Returns 0.0 for unknown assumption names (defensive default).
    """

    default = get_default_value(assumption_name)
    if default is None:
        return 0.0

    if assumption_name == "otd_carrier_buffer_pct":
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    return 0.0 if value == default else 1.0


def validate_value(assumption_name: str, value: Any) -> None:
    """Raise ValueError if `value` is not permitted for `assumption_name`."""

    if assumption_name not in V1_CATALOG:
        raise ValueError(f"Unknown assumption_name: {assumption_name!r}")

    entry = V1_CATALOG[assumption_name]
    allowed = entry.get("allowed_values")

    if allowed is not None and value not in allowed:
        raise ValueError(
            f"Value {value!r} not allowed for {assumption_name!r}. "
            f"Allowed: {allowed}"
        )

    # Special-case numeric validation for otd_carrier_buffer_pct.
    if assumption_name == "otd_carrier_buffer_pct":
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"otd_carrier_buffer_pct must be numeric, got {value!r}"
            ) from exc
        if not (0.0 <= numeric <= 100.0):
            raise ValueError(
                f"otd_carrier_buffer_pct must be in [0, 100], got {numeric}"
            )
