"""
Metric metadata for the Phase 4 inspector UI.

Static, engineering-curated. The inspector UI calls this to render the formula
text alongside each historical calculation result. Formulas are written as
human-readable text rather than LaTeX so the same string works in both web and
print/CSV exports.
"""

from typing import TypedDict


class MetricMetadata(TypedDict):
    name: str
    formula: str
    description: str
    inputs_help: dict[str, str]


METRIC_METADATA: dict[str, MetricMetadata] = {
    "oee": {
        "name": "Overall Equipment Effectiveness",
        "formula": "OEE = (Availability% × Performance% × Quality%) / 10000",
        "description": (
            "Composite measure of how effectively a production line is utilized "
            "relative to its full potential."
        ),
        "inputs_help": {
            "scheduled_hours": "Hours the line was scheduled to produce.",
            "downtime_hours": "Hours the line was down (planned + unplanned).",
            "setup_minutes": "Minutes spent on setup/changeovers within the period.",
            "scheduled_maintenance_hours": "Hours of planned maintenance within the period.",
            "units_produced": "Units produced over run_time_hours.",
            "run_time_hours": "Hours the line was actually running.",
            "ideal_cycle_time_hours": "Engineering-standard hours per unit.",
            "defect_count": "Units flagged as defective at inspection.",
            "scrap_count": "Units scrapped (unrecoverable).",
            "units_reworked": "Units corrected in-line after failing inspection.",
        },
    },
    "otd": {
        "name": "On-Time Delivery",
        "formula": "OTD% = (Orders delivered on or before planned date / Total orders) × 100",
        "description": (
            "Percentage of customer orders delivered by the planned date. "
            "When the otd_carrier_buffer_pct assumption is active, the on-time "
            "window is extended by that percentage of the order's lead time."
        ),
        "inputs_help": {
            "orders": "List of completed orders with delay_pct (delay as fraction of lead time).",
        },
    },
    "fpy": {
        "name": "First Pass Yield",
        "formula": "FPY% = (Units passed first time / Total units inspected) × 100",
        "description": (
            "Fraction of units that pass inspection on the first attempt. "
            "Whether reworked units count as 'passed' depends on the "
            "scrap_classification_rule assumption."
        ),
        "inputs_help": {
            "total_inspected": "Total units inspected over the period.",
            "units_passed_first_time": "Units that passed without rework or repair.",
            "units_reworked": "Units that initially failed but were corrected in-line.",
        },
    },
}


def get_metadata(metric_name: str) -> MetricMetadata | None:
    return METRIC_METADATA.get(metric_name)
