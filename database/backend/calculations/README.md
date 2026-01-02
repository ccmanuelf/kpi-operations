# Backend Calculations Module

This module contains KPI calculation functions for production metrics.

## Modules

### `efficiency.py` - Workforce Efficiency Calculation (KPI #3)

Calculates workforce efficiency using SCHEDULED shift hours.

**Formula:**
```
Efficiency = (Units Produced × Ideal Cycle Time) / (Employees Assigned × SCHEDULED Hours) × 100
```

**Key Functions:**
- `calculate_shift_hours(shift_start, shift_end)` - Calculate scheduled hours from shift times
- `calculate_efficiency(units, cycle_time, employees, shift_hours)` - Pure calculation function
- `calculate_efficiency_from_db(db, entry_id)` - Database integration
- `update_efficiency_in_db(db, entry_id)` - Update production entries

**Example:**
```python
from backend.calculations import calculate_efficiency

efficiency = calculate_efficiency(
    units_produced=1000,
    ideal_cycle_time=0.01,
    employees_assigned=5,
    shift_hours=8.0  # SCHEDULED hours from shift definition
)
# Returns: 25.0 (25% efficiency)
```

### `performance.py` - Machine Performance Calculation (KPI #9)

Calculates machine/line performance using ACTUAL runtime hours.

**Formula:**
```
Performance = (Units Produced × Ideal Cycle Time) / Runtime Hours × 100
```

**Key Functions:**
- `calculate_performance(units, cycle_time, run_time_hours)` - Pure calculation function
- `calculate_performance_from_db(db, entry_id)` - Database integration

**Example:**
```python
from backend.calculations import calculate_performance

performance = calculate_performance(
    units_produced=1000,
    ideal_cycle_time=0.01,
    run_time_hours=6.0  # ACTUAL runtime hours
)
# Returns: 166.67 (166.67% performance)
```

## Key Difference: Efficiency vs Performance

| Metric | Denominator | What It Measures |
|--------|-------------|------------------|
| **Efficiency** | Employees × SCHEDULED shift hours | Workforce utilization during planned time |
| **Performance** | ACTUAL runtime hours | Machine speed during operation |

**Example Scenario:**
- 8-hour scheduled shift
- 6 hours actual runtime (2 hours downtime)
- 1000 units, 5 employees

```python
efficiency = (1000 × 0.01) / (5 × 8) = 25%     # Uses scheduled 8 hours
performance = (1000 × 0.01) / 6 = 166.67%      # Uses runtime 6 hours
```

**Key Insight:**
- Efficiency stays constant regardless of downtime (measures workforce, not machine)
- Performance changes with downtime (measures machine speed)

## Usage

### Direct Calculation
```python
from backend.calculations import calculate_efficiency, calculate_performance

# Efficiency
eff = calculate_efficiency(
    units_produced=1000,
    ideal_cycle_time=0.01,
    employees_assigned=5,
    shift_hours=8.0
)

# Performance
perf = calculate_performance(
    units_produced=1000,
    ideal_cycle_time=0.01,
    run_time_hours=6.0
)
```

### Database Integration
```python
from backend.calculations.efficiency import calculate_efficiency_from_db
from backend.calculations.performance import calculate_performance_from_db

# Calculate from database entry
efficiency = calculate_efficiency_from_db(db_session, entry_id=123)
performance = calculate_performance_from_db(db_session, entry_id=123)
```

### Update Database
```python
from backend.calculations.efficiency import update_efficiency_in_db

# Calculate and update
success = update_efficiency_in_db(db_session, entry_id=123)
```

## Testing

Run the test suite:
```bash
pytest tests/test_efficiency_calculation.py -v
```

## Documentation

- **Detailed Fix:** `/docs/EFFICIENCY_FORMULA_FIX.md`
- **Quick Summary:** `/docs/EFFICIENCY_FIX_SUMMARY.md`
- **Developer Reference:** `/docs/EFFICIENCY_VS_PERFORMANCE_REFERENCE.md`

## Requirements

- Python 3.8+
- SQLAlchemy (for database integration)
- pytest (for testing)

## Important Notes

1. **NEVER use runtime hours for efficiency** - Always use scheduled shift hours
2. **Efficiency is independent of downtime** - It measures workforce, not machine
3. **Validate inputs** - All functions return `None` for invalid inputs (zero/negative values)
4. **Handle overnight shifts** - Shift calculation handles shifts crossing midnight

## See Also

- SQL stored procedures: `/database/schema.sql` (lines 212-266)
- Test suite: `/tests/test_efficiency_calculation.py`
- Database models: `/backend/models.py` (when created)
