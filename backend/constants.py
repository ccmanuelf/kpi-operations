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

LOOKBACK_DAILY_HOURS = 24
"""24 hours lookback for recent alerts"""


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


# ==================== CAPACITY PLANNING ====================
# Capacity planning specific constants

DEFAULT_MAX_OPERATORS = 10
"""Default maximum operators for capacity calculations"""
