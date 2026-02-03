"""
Production Line Simulation v2.0 - Constants and Defaults

Central location for all default values, thresholds, and configuration limits.
These values match the technical specification v2.0.
"""

# =============================================================================
# VERSION
# =============================================================================

ENGINE_VERSION = "2.0.0"

# =============================================================================
# CONFIGURATION LIMITS
# =============================================================================

MAX_PRODUCTS = 5
MAX_OPERATIONS_PER_PRODUCT = 50
MAX_TOTAL_OPERATIONS = 100
MAX_HORIZON_DAYS = 7
MAX_BUNDLE_SIZE = 100
MAX_OPERATORS_PER_STATION = 20

# =============================================================================
# OPERATION DEFAULTS
# =============================================================================

DEFAULT_SEQUENCE = "Assembly"
DEFAULT_GROUPING = ""
DEFAULT_OPERATORS = 1
DEFAULT_VARIABILITY = "triangular"
DEFAULT_REWORK_PCT = 0.0
DEFAULT_GRADE_PCT = 85.0
DEFAULT_FPD_PCT = 15.0

# =============================================================================
# SCHEDULE DEFAULTS
# =============================================================================

DEFAULT_SHIFTS_ENABLED = 1
DEFAULT_SHIFT_HOURS = 8.0
DEFAULT_WORK_DAYS = 5
DEFAULT_OT_ENABLED = False

# =============================================================================
# DEMAND DEFAULTS
# =============================================================================

DEFAULT_BUNDLE_SIZE = 1
DEFAULT_HORIZON_DAYS = 1

# =============================================================================
# BOTTLENECK DETECTION THRESHOLDS
# =============================================================================

BOTTLENECK_UTILIZATION_THRESHOLD = 95.0  # >= this is a bottleneck
DONOR_UTILIZATION_THRESHOLD = 70.0       # <= this is a potential donor (if operators > 1)

# =============================================================================
# STATUS DETERMINATION THRESHOLDS (Block 1)
# =============================================================================

COVERAGE_OK_THRESHOLD = 110.0      # >= this is "OK" (surplus capacity)
COVERAGE_TIGHT_THRESHOLD = 90.0    # >= this and < OK is "Tight"
# < TIGHT is "Shortfall"

# =============================================================================
# BUNDLE TRANSITION TIMES (in seconds)
# =============================================================================

SMALL_BUNDLE_THRESHOLD = 5  # Bundles <= this use small transition time
SMALL_BUNDLE_TRANSITION_SECONDS = 1.0
LARGE_BUNDLE_TRANSITION_SECONDS = 5.0

# =============================================================================
# VARIABILITY PARAMETERS
# =============================================================================

TRIANGULAR_VARIABILITY_MIN = -0.10  # -10%
TRIANGULAR_VARIABILITY_MAX = 0.10   # +10%
TRIANGULAR_VARIABILITY_MODE = 0.0   # Centered at 0

# =============================================================================
# PROCESSING TIME FORMULA CONSTANTS
# =============================================================================

MIN_PROCESS_TIME_MINUTES = 0.01  # Minimum processing time to prevent zero/negative

# =============================================================================
# VALIDATION THRESHOLDS
# =============================================================================

DEMAND_CONSISTENCY_TOLERANCE_PCT = 5.0  # Warning if daily*workdays differs from weekly by this %
MIX_PERCENTAGE_TOLERANCE = 0.1  # Sum of mix percentages must be within this of 100
MACHINE_TOOL_SIMILARITY_THRESHOLD = 0.8  # Warn if tool names are this similar but not identical
THEORETICAL_CAPACITY_BUFFER = 1.1  # Warn if theoretical hours needed > available * this

# =============================================================================
# WIP SAMPLING
# =============================================================================

WIP_SAMPLE_INTERVAL_MINUTES = 5.0  # How often to sample WIP during simulation

# =============================================================================
# FORMULA DESCRIPTIONS (for Block 8 Assumption Log)
# =============================================================================

FORMULA_DESCRIPTIONS = {
    "processing_time": "SAM × (1 + Variability + FPD_pct/100 + (100-Grade_pct)/100)",
    "bundle_transition": f"{SMALL_BUNDLE_TRANSITION_SECONDS}s if bundle_size ≤ {SMALL_BUNDLE_THRESHOLD}, else {LARGE_BUNDLE_TRANSITION_SECONDS}s",
    "utilization": "(Busy_Time / Available_Time) × 100",
    "bottleneck_detection": f"Utilization >= {BOTTLENECK_UTILIZATION_THRESHOLD}%",
    "donor_detection": f"Utilization <= {DONOR_UTILIZATION_THRESHOLD}% AND operators > 1",
}

# =============================================================================
# LIMITATIONS AND CAVEATS (for Block 8 Assumption Log)
# =============================================================================

SIMULATION_LIMITATIONS = [
    "Single replication run - results represent one possible outcome",
    "Weekly capacity assumes uniform daily production without day-of-week effects",
    "Learning curves and dynamic skill improvements are not modeled",
    "Material availability and supply chain constraints are assumed perfect",
    "Quality costs are included but not second-order effects like operator morale",
    "Bundle rework extracts single pieces; rest of bundle continues forward",
    "Equipment breakdowns add fixed delay; no progressive degradation modeled",
]
