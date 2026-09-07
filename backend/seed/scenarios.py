"""Declarative per-client scenarios: who exists, and what story their data
tells. Pure configuration -- no generation logic, no database.

Four clients, each demonstrating a different failure mode, plus one healthy
control so the dashboards are not uniformly red (spec section 6).

Also carries the vocabulary the later stages consume verbatim: catalog codes,
credentials, and per-client products. The vocabulary constants were read off
the live VM (2026-08-17) -- not invented -- because a display name where a
code belongs is how the current dataset ended up with a defect taxonomy that
joins to nothing (all 80 live DEFECT_DETAIL rows say "Stitching").
"""

from dataclasses import dataclass

#: Live VM vocabulary (2026-08-17). Do not invent synonyms.
CLIENT_TYPE_BY_PAY_MODEL = {
    "piece": "Piece Rate",
    "hourly": "Hourly Rate",
    "hybrid": "Hybrid",
}
LINE_TYPE = "DEDICATED"
UNIT_OF_MEASURE = "units"
WORK_ORDER_ORIGINS = ("AD_HOC", "CAPACITY_PLAN")
DOWNTIME_REASONS = (
    "EQUIPMENT_FAILURE",
    "MAINTENANCE",
    "MATERIAL_SHORTAGE",
    "OPERATOR_UNAVAILABLE",
    "QUALITY_HOLD",
    "SETUP_CHANGEOVER",
)
ROOT_CAUSES = ("attendance", "machine", "materials", "other", "scheduling")
DEFECT_CODES = ("COLOR", "FABRIC", "MEASURE", "STAIN", "STITCH")

# --- INVENTED VOCABULARY: the routing --------------------------------------
# This module's docstring says its vocabulary was read off the live VM
# (2026-08-17). The three constants between this banner and its closing one are
# the exception, and are banner-flagged so a reader can tell the two kinds apart
# at a glance: nothing in the live dataset, in any CSV inventory or in any
# migration describes a routing, so a JOB row cannot be reconstructed from
# observed data the way a defect code or a downtime reason can. It is invented.

#: (operation_code, operation_name) in the order a work order walks them. One
#: generic sequence for every client and every product: the platform models no
#: per-product routing (JOB is the only table that mentions an operation at
#: all, and it stores the operation as free text on the row), so a per-client
#: routing would be inventing MORE than the data supports, not less.
ROUTING = (
    ("PREP", "Preparation"),
    ("BUILD", "Build"),
    ("FINISH", "Finishing"),
    ("PACK", "Packing"),
)

#: Hours per unit used to derive JOB.planned_hours. NOT a free parameter: it is
#: the cycle time the application itself resolves for every seeded product.
#: Seeded PRODUCT rows carry no ideal_cycle_time (writers_master.py writes the
#: five columns the catalog needs and no estimate), so
#: ProductionKPIService.calculate_efficiency_only falls through to
#: backend/calculations/efficiency.py's DEFAULT_CYCLE_TIME for every seeded
#: production entry. Deriving planned_hours from anything else would put a
#: second, competing labor content next to the ONE efficiency formula the
#: platform has -- (units * ideal_cycle_time) / (employees * scheduled_hours).
#:
#: Duplicated as a literal rather than imported: backend/seed/ may not import
#: backend.calculations (tests/test_seed/test_purity.py). The two are pinned
#: equal by tests/test_seed/test_jobs.py.
IDEAL_CYCLE_TIME_HOURS = 0.25

#: Units scrapped per hundred finished at a routing step. Invented, and it must
#: be non-zero: JOB.quantity_scrapped is the entire numerator of
#: GET /api/jobs/{job_id}/yield, so a routing that scraps nothing reports
#: exactly 100.00% for every job and demonstrates nothing about the metric.
SCRAP_UNITS_PER_HUNDRED = 1

# --- end invented vocabulary; everything below is live-VM vocabulary again ---

#: (code, display name, category, severity) -- the catalog every client gets.
DEFECT_CATALOG = (
    ("COLOR", "Color Variation", "VISUAL", "MINOR"),
    ("FABRIC", "Fabric Flaw", "MATERIAL", "MAJOR"),
    ("MEASURE", "Measurement Out of Tolerance", "DIMENSIONAL", "MAJOR"),
    ("STAIN", "Stain or Soil", "VISUAL", "MINOR"),
    ("STITCH", "Stitching Defect", "VISUAL", "MAJOR"),
)

#: Which downtime reason each root cause explains. The narrative biases the
#: ROOT CAUSE (spec section 6: DEMO-HOURLY must read as equipment reliability,
#: and the Q4 correlation block needs scheduling-category downtime); the reason
#: follows from it, so the two can never disagree.
REASON_BY_ROOT_CAUSE = {
    "attendance": "OPERATOR_UNAVAILABLE",
    "machine": "MAINTENANCE",
    "materials": "MATERIAL_SHORTAGE",
    "other": "QUALITY_HOLD",
    "scheduling": "SETUP_CHANGEOVER",
}

#: The same map with the machine category written as a FAILURE rather than as
#: routine maintenance, used while an equipment-reliability-decline window is
#: open.
#:
#: MAINTENANCE and SETUP_CHANGEOVER are the two members of
#: PLANNED_DOWNTIME_REASONS (backend/orm/downtime_taxonomy.py:53). The one
#: consumer that filters on that set is calculate_mtbf
#: (backend/calculations/availability.py:87), which excludes them because it
#: counts FAILURES and planned work is not one.
#:
#: (The x3 minute scale still reaches the client's Availability reading, but
#: NOT through calculate_availability: that function filters
#: DowntimeEntry.work_order_id (availability.py:38) and calculate_mttr
#: filters machine_id (availability.py:127), and the seeder leaves both
#: columns NULL -- measured, not assumed: calculate_availability returns
#: (100, 8.0, 0, 0) and MTTR/MTBF return None for every seeded work order and
#: machine. The minutes are seen by the consumers that aggregate downtime by
#: client and date instead -- dashboard, trends, downtime and my_shift --
#: which is why S1b defers work_order_id/machine_id on DOWNTIME_ENTRY rather
#: than treating it as a gap.) A reliability decline recorded
#: entirely as MAINTENANCE therefore produces ZERO failures: MTBF, the metric
#: named for the thing the narrative is about, cannot move at all, and the
#: decline reads as scheduled servicing -- the opposite of the story spec
#: section 6 asks DEMO-HOURLY to tell. EQUIPMENT_FAILURE is the same `machine`
#: category (the first entry of DEFAULT_CATEGORY_BY_REASON) and is unplanned,
#: so the 1:1 map above cannot reach it and needs this override.
UNPLANNED_REASON_BY_ROOT_CAUSE = {
    **REASON_BY_ROOT_CAUSE,
    "machine": "EQUIPMENT_FAILURE",
}

HOLD_REASONS = (
    ("QUALITY", "Quality Issue", True),
    ("MATERIAL", "Material Shortage", False),
    ("ENGINEERING", "Engineering Change", False),
)
HOLD_STATUSES = (
    ("PENDING_HOLD_APPROVAL", "Pending Hold Approval", True),
    ("ON_HOLD", "On Hold", False),
    ("PENDING_RESUME_APPROVAL", "Pending Resume Approval", False),
    ("RESUMED", "Resumed", False),
)

#: kpi_key -> target, emitted once per client. KPI_THRESHOLD.client_id is a
#: real (nullable, but populated here) FK under
#: UniqueConstraint(client_id, kpi_key) -- these are per-tenant defaults, not
#: global rows, so emitters_master.py emits one full set for every scenario.
THRESHOLDS = (
    ("efficiency", 85.0),
    ("otd", 95.0),
    ("fpy", 97.0),
    ("oee", 75.0),
)

#: One constant, documented in the deployment runbook.
DEMO_PASSWORD = "DemoSeed#2026"  # pragma: allowlist secret

#: Who every seeded PRODUCTION_ENTRY.entered_by and transition is attributed
#: to. A real user_id, not a literal sprinkled through the generator: the
#: column is a foreign key to USER, and a string that resolves to no user
#: leaves the "who entered this" column pointing at nobody.
#:
#: PLATFORM-SCOPED deliberately, and renamed from SUPERVISOR_USER_ID for it.
#: The demo supervisor is granted DEMO-PIECE alone, so attributing all four
#: tenants' production to them puts "Demo Supervisor" on SAMPLE_REF rows --
#: not a foreign-key error, but in a product whose client-scope authorization
#: was just made uniform it reads as a tenant-isolation bug. The admin belongs
#: to no tenant (client_ids == ()), so attributing to them crosses no scope.
ATTRIBUTION_USER_ID = "USR-DEMO-ADMIN"


@dataclass(frozen=True)
class UserSpec:
    user_id: str
    username: str
    role: str
    full_name: str
    client_ids: tuple[str, ...]  # () means platform-wide (no tenant scope)


USERS = (
    UserSpec("USR-DEMO-ADMIN", "demo_admin", "admin", "Demo Administrator", ()),
    UserSpec("USR-DEMO-PLANNER", "demo_planner", "poweruser", "Demo Planner", ()),
    UserSpec(
        "USR-DEMO-LEADER",
        "demo_leader",
        "leader",
        "Demo Area Leader",
        ("DEMO-PIECE", "DEMO-HOURLY", "DEMO-HYBRID"),
    ),
    UserSpec("USR-DEMO-SUP", "demo_supervisor", "supervisor", "Demo Supervisor", ("DEMO-PIECE",)),
    UserSpec("USR-DEMO-OP", "demo_operator", "operator", "Demo Operator", ("DEMO-PIECE",)),
    UserSpec("USR-DEMO-VIEW", "demo_viewer", "viewer", "Demo Viewer", ("DEMO-PIECE",)),
)


@dataclass(frozen=True)
class ProductSpec:
    code: str
    name: str
    style: str


@dataclass(frozen=True)
class NarrativeWindow:
    """A scripted episode. Months are negative offsets from the seed's as-of
    date: start_month=-8, end_month=-6 means "eight to six months ago"."""

    kind: str
    start_month: int
    end_month: int


@dataclass(frozen=True)
class ClientScenario:
    client_id: str
    name: str
    pay_model: str
    client_type: str
    products: tuple[ProductSpec, ...]
    narrative: tuple[NarrativeWindow, ...]


SCENARIOS = (
    ClientScenario(
        client_id="DEMO-PIECE",
        name="Piecework Apparel Co.",
        pay_model="piece",
        client_type="Piece Rate",
        products=(
            ProductSpec("PC-SHIRT", "Classic Shirt", "STYLE-1"),
            ProductSpec("PC-PANT", "Work Pant", "STYLE-2"),
            ProductSpec("PC-JACK", "Field Jacket", "STYLE-3"),
        ),
        narrative=(NarrativeWindow(kind="supplier_quality_crisis", start_month=-8, end_month=-6),),
    ),
    ClientScenario(
        client_id="DEMO-HOURLY",
        name="Hourly Components Ltd.",
        pay_model="hourly",
        client_type="Hourly Rate",
        products=(
            ProductSpec("HR-BRKT", "Mounting Bracket", "STYLE-1"),
            ProductSpec("HR-HOUS", "Motor Housing", "STYLE-2"),
            ProductSpec("HR-PANEL", "Control Panel", "STYLE-3"),
        ),
        narrative=(NarrativeWindow(kind="equipment_reliability_decline", start_month=-5, end_month=-3),),
    ),
    ClientScenario(
        client_id="DEMO-HYBRID",
        name="Hybrid Assembly Group",
        pay_model="hybrid",
        client_type="Hybrid",
        products=(
            ProductSpec("HY-FRAME", "Chassis Frame", "STYLE-1"),
            ProductSpec("HY-SUB", "Sub-Assembly Kit", "STYLE-2"),
            ProductSpec("HY-FIN", "Finished Unit", "STYLE-3"),
        ),
        narrative=(NarrativeWindow(kind="labor_disruption", start_month=-4, end_month=-2),),
    ),
    # The control. Every metric stays in specification for the full year, so a
    # demo can show a healthy client beside three troubled ones and the
    # thresholds read as informative rather than broken.
    ClientScenario(
        client_id="SAMPLE_REF",
        name="Reference Manufacturing",
        pay_model="hourly",
        client_type="Hourly Rate",
        products=(
            ProductSpec("RF-WIDGET", "Reference Widget", "STYLE-1"),
            ProductSpec("RF-GADGET", "Reference Gadget", "STYLE-2"),
            ProductSpec("RF-PART", "Reference Part", "STYLE-3"),
        ),
        narrative=(),
    ),
)

#: The site's calculation assumptions, as VALUES drawn from
#: `services/calculations/assumption_catalog.V1_CATALOG`.
#:
#: Restated here rather than imported: that module imports
#: `sqlalchemy.orm.Session` at module level, and the purity guard forbids the
#: seed engine from importing database machinery. Restating risks drift, so
#: `test_assumption_specs_match_the_catalog` asserts every name exists in the
#: catalog and every value is one the catalog permits -- the two-sided pattern
#: this package already uses for enums.
#:
#: Two of the six deviate from `default_value` ON PURPOSE. The dual-view
#: feature exists to show standard-versus-site-adjusted numbers; if every
#: assumption matched the textbook default, both views would be identical and
#: the delta column would be zero everywhere.
#:
#: WHICH two is not arbitrary. A deviation only moves a number if the rule
#: behind it reads a column with something in it, and if the service can
#: actually apply it. The two that deviate are the two whose inputs the seeder
#: writes: scheduled maintenance and setup time.
#:
#: `ideal_cycle_time_source="demonstrated_best"` was rejected here because it
#: was INERT -- oee_service applies it only when
#: `demonstrated_best_cycle_time_hours` is set, and `aggregate_oee_inputs`
#: never set that field on any production path, so it would have deviated
#: while changing nothing. That is fixed (issue #278): the aggregator now
#: computes both alternative cycle times, and on this dataset a
#: demonstrated-best cycle is ~12% faster than the period standard, which
#: moves OEE by roughly -12 points.
#:
#: It is still NOT the assumption seeded here, deliberately. Switching to it
#: would drop the demo's headline OEE from ~94 to ~80 -- an honest number, but
#: a different demo, and that is a product decision rather than a consequence
#: of fixing the bug. `rolling_90_day_average` is a worse candidate again: the
#: seeded run rate is stationary, so a trailing window sits within ~1% of any
#: period and the delta rounds to nothing.
#:
#: The catalog default travels with each row so the change history can say
#: what the value moved AWAY from. It cannot be imported: assumption_catalog
#: pulls in sqlalchemy.orm.Session. test_assumption_dataset pins it against
#: V1_CATALOG, so a drifting default fails rather than seeds a false trail.
#:
#: (assumption_name, value, default_value, deviates_from_default, rationale)
CALCULATION_ASSUMPTIONS = (
    (
        "planned_production_time_basis",
        "exclude_scheduled_maintenance",
        "include_scheduled_maintenance",
        True,
        "Planned maintenance is scheduled outside production windows here, so counting it as "
        "available time understates availability.",
    ),
    (
        "ideal_cycle_time_source",
        "engineering_standard",
        "engineering_standard",
        False,
        "Engineering standards are current for this line; no demonstrated-best study has been "
        "completed, so the standard remains the reference.",
    ),
    (
        "setup_treatment",
        "exclude_from_availability",
        "count_as_downtime",
        True,
        "Changeovers are planned into the schedule rather than lost to it, so counting them as "
        "downtime understates what these lines can deliver.",
    ),
    (
        "scrap_classification_rule",
        "rework_counted_as_good",
        "rework_counted_as_good",
        False,
        "Textbook default retained: reworked units ship and are counted good.",
    ),
    (
        "otd_carrier_buffer_pct",
        0,
        0,
        False,
        "No carrier buffer negotiated; delivery is judged against the planned date itself.",
    ),
    (
        "yield_baseline_source",
        "theoretical",
        "theoretical",
        False,
        "Textbook default retained pending a demonstrated baseline study.",
    ),
)
