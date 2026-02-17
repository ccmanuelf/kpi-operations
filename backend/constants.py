"""
Backend Constants (CQ-23)
Application-wide constants for pagination, time windows, and validation limits.
Extracted from magic numbers across routes, services, and CRUD operations.
"""

# ==================== PAGINATION ====================
# Default page sizes for list endpoints
# Used across 30+ routes for consistent pagination behavior

DEFAULT_PAGE_SIZE = 100
"""Default number of records to return in paginated responses"""

SMALL_PAGE_SIZE = 10
"""Small page size for summaries and recent items (KPI, my_shift)"""

MEDIUM_PAGE_SIZE = 50
"""Medium page size for alerts and filtered lists"""

LARGE_PAGE_SIZE = 500
"""Large page size for bulk data (orders, stock, workflows)"""

EXTRA_LARGE_PAGE_SIZE = 1000
"""Extra large page size for reference data (standards, catalog)"""

MAX_PAGE_SIZE = 500
"""Maximum allowed page size to prevent performance issues"""

MAX_ALERT_PAGE_SIZE = 200
"""Maximum page size for alerts endpoint"""

# Calendar and planning horizons
CALENDAR_DEFAULT_DAYS = 365
"""Default calendar entries to fetch (one year)"""


# ==================== TIME WINDOWS ====================
# Lookback periods for data queries and analytics

LOOKBACK_WEEKLY_DAYS = 7
"""One week lookback for short-term trends"""

LOOKBACK_MONTHLY_DAYS = 30
"""One month lookback for medium-term analysis"""

LOOKBACK_QUARTERLY_DAYS = 90
"""Three months lookback for quarterly reports"""

LOOKBACK_YEARLY_DAYS = 365
"""One year lookback for annual trends"""

LOOKBACK_DAILY_HOURS = 24
"""24 hours lookback for recent alerts"""

DEFAULT_REPORT_DAYS = 30
"""Default historical period for reports"""


# ==================== QUERY VALIDATION LIMITS ====================
# Min/max constraints for query parameters

# Days constraints
MIN_DAYS_LOOKBACK = 1
"""Minimum days for lookback queries"""

MAX_DAYS_SHORT = 90
"""Maximum days for short-term queries (alerts, etc.)"""

MAX_DAYS_LONG = 365
"""Maximum days for long-term queries (yearly trends)"""

MIN_HISTORICAL_DAYS = 7
"""Minimum historical data window for predictions"""

MAX_HISTORICAL_DAYS = 90
"""Maximum historical data window for predictions"""

# Forecast constraints
MIN_FORECAST_DAYS = 1
"""Minimum forecast horizon"""

MAX_FORECAST_DAYS = 30
"""Maximum forecast horizon (one month)"""

# Shift constraints
MIN_SHIFT_NUMBER = 1
"""Minimum shift number (first shift)"""

MAX_SHIFT_NUMBER = 3
"""Maximum shift number (third shift)"""


# ==================== SIMULATION DEFAULTS ====================
# Default values for production simulation endpoints

DEFAULT_SHIFT_HOURS = 8.0
"""Standard 8-hour work shift"""

MAX_SHIFT_HOURS = 24.0
"""Maximum shift hours (full day)"""

DEFAULT_CYCLE_TIME_HOURS = 0.25
"""Default cycle time: 15 minutes (0.25 hours)"""

DEFAULT_EFFICIENCY_PERCENT = 85.0
"""Default production efficiency (85%)"""

MIN_EFFICIENCY_PERCENT = 0.0
"""Minimum efficiency (0%)"""

MAX_EFFICIENCY_PERCENT = 100.0
"""Maximum efficiency (100%)"""

DEFAULT_RANDOM_SEED = 42
"""Default random seed for reproducible simulations"""

# Station configuration
DEFAULT_NUM_STATIONS = 4
"""Default number of work stations"""

MIN_NUM_STATIONS = 2
"""Minimum number of work stations"""

MAX_NUM_STATIONS = 10
"""Maximum number of work stations"""

DEFAULT_WORKERS_PER_STATION = 2
"""Default workers per station"""

MIN_WORKERS_PER_STATION = 1
"""Minimum workers per station"""

MAX_WORKERS_PER_STATION = 10
"""Maximum workers per station"""

DEFAULT_FLOATING_POOL_SIZE = 0
"""Default floating pool size (none)"""

MAX_FLOATING_POOL_SIZE = 10
"""Maximum floating pool size"""

DEFAULT_BASE_CYCLE_TIME_MINUTES = 15.0
"""Default base cycle time in minutes"""

MAX_BASE_CYCLE_TIME_MINUTES = 120.0
"""Maximum base cycle time in minutes"""


# ==================== UI CONFIGURATION ====================
# QR code and image generation

DEFAULT_QR_SIZE_PIXELS = 200
"""Default QR code size in pixels"""

MIN_QR_SIZE_PIXELS = 100
"""Minimum QR code size"""

MAX_QR_SIZE_PIXELS = 500
"""Maximum QR code size"""


# ==================== ANALYTICS ====================
# Analytics and reporting thresholds

DEFAULT_PARETO_THRESHOLD_PERCENT = 80.0
"""Default Pareto threshold (80/20 rule)"""

MIN_PARETO_THRESHOLD_PERCENT = 50.0
"""Minimum Pareto threshold"""

MAX_PARETO_THRESHOLD_PERCENT = 95.0
"""Maximum Pareto threshold"""


# ==================== CAPACITY PLANNING ====================
# Capacity planning specific constants

DEFAULT_MAX_OPERATORS = 10
"""Default maximum operators for capacity calculations"""

SCHEDULING_LOOKAHEAD_DAYS = 7
"""Days to lookahead for scheduling priority orders"""


# ==================== SYSTEM HEALTH ====================
# Health check and monitoring

CPU_SAMPLE_INTERVAL_SECONDS = 0.1
"""CPU sampling interval for health checks (100ms)"""


# ==================== OPERATOR CONSTRAINTS ====================
# Production line operator limits

MIN_OPERATORS = 1
"""Minimum operators for a production line"""

MAX_OPERATORS_DEFAULT = 10
"""Default maximum operators per production line"""


# ==================== BACKWARD COMPATIBILITY ALIASES ====================
# Legacy names for gradual migration

# Pagination aliases
PAGINATION_DEFAULT_LIMIT = DEFAULT_PAGE_SIZE
PAGINATION_MAX_LIMIT = MAX_PAGE_SIZE

# Time window aliases
DEFAULT_LOOKBACK_DAYS = LOOKBACK_MONTHLY_DAYS
