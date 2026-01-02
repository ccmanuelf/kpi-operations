# Quick Reference: Efficiency vs Performance

## 🎯 TL;DR

| Metric | Formula | Denominator | What It Measures |
|--------|---------|-------------|------------------|
| **Efficiency** | `(Units × Cycle Time) / (Employees × SCHEDULED Hours)` | Scheduled shift hours | Workforce utilization during planned time |
| **Performance** | `(Units × Cycle Time) / RUNTIME Hours` | Actual runtime | Machine speed during operation |

## ✅ DO's and DON'Ts

### ✅ Efficiency (KPI #3)
```python
# ✅ CORRECT: Use scheduled shift hours
efficiency = calculate_efficiency(
    units_produced=1000,
    ideal_cycle_time=0.01,
    employees_assigned=5,
    shift_hours=8.0  # ← SCHEDULED hours from shift definition
)
```

```python
# ❌ WRONG: Don't use runtime hours
efficiency = calculate_efficiency(
    units_produced=1000,
    ideal_cycle_time=0.01,
    employees_assigned=5,
    shift_hours=6.0  # ← Don't use actual runtime!
)
```

### ✅ Performance (KPI #9)
```python
# ✅ CORRECT: Use actual runtime hours
performance = calculate_performance(
    units_produced=1000,
    ideal_cycle_time=0.01,
    run_time_hours=6.0  # ← RUNTIME hours (actual operation time)
)
```

## 📊 Real-World Example

**Scenario:**
- Shift: 07:00 to 15:00 (8 scheduled hours)
- Actual runtime: 6 hours (2 hours downtime for maintenance)
- Units produced: 1000
- Ideal cycle time: 0.01 hours/unit
- Employees: 5

### Calculations:

**Efficiency:**
```
(1000 × 0.01) / (5 × 8) = 10 / 40 = 0.25 = 25%
                    ↑
            Uses SCHEDULED 8 hours
```

**Performance:**
```
(1000 × 0.01) / 6 = 10 / 6 = 1.667 = 166.7%
                ↑
        Uses RUNTIME 6 hours
```

### Interpretation:
- **25% Efficiency:** Workforce utilized 25% of available scheduled time productively
- **167% Performance:** Machine ran 67% faster than ideal when operating

## 🤔 Why Different Denominators?

### Efficiency Measures: **Workforce Utilization**
- **Question:** How well did employees use their scheduled time?
- **Denominator:** Total scheduled hours (employees × shift hours)
- **Not affected by:** Machine downtime, maintenance, material delays
- **Affected by:** Number of employees, shift duration, output quantity

### Performance Measures: **Machine Speed**
- **Question:** How fast did the machine run when operating?
- **Denominator:** Actual runtime hours (machine operating time)
- **Not affected by:** Number of employees, shift length
- **Affected by:** Machine speed, downtime, output quantity

## 🔍 Key Differences

| Aspect | Efficiency | Performance |
|--------|-----------|-------------|
| **Measures** | Workforce productivity | Machine/line speed |
| **Time Base** | Scheduled shift hours | Actual runtime |
| **Includes Employees?** | Yes (in denominator) | No |
| **Affected by Downtime?** | No | Yes (indirectly) |
| **Typical Values** | 10%-80% | 50%-200%+ |
| **Low Value Means** | Poor workforce utilization | Slow machine operation |
| **High Value Means** | Efficient workforce | Fast machine operation |

## 💡 Common Scenarios

### Scenario 1: High Efficiency, Low Performance
```
Efficiency: 80% (excellent workforce utilization)
Performance: 60% (machine running slowly)
```
**Interpretation:** Workers are productive, but machine needs optimization

### Scenario 2: Low Efficiency, High Performance
```
Efficiency: 20% (poor workforce utilization)
Performance: 150% (machine running fast)
```
**Interpretation:** Machine is fast, but workforce is underutilized (too many employees or long shift)

### Scenario 3: Both High
```
Efficiency: 70%
Performance: 140%
```
**Interpretation:** Optimal operation - workforce productive and machine running well

### Scenario 4: Both Low
```
Efficiency: 15%
Performance: 50%
```
**Interpretation:** Multiple issues - workforce underutilized and machine slow

## 🧮 Quick Calculation Formulas

### Efficiency
```
Standard Hours Produced = Units × Cycle Time
Available Hours = Employees × Scheduled Shift Hours
Efficiency = (Standard Hours / Available Hours) × 100%
```

### Performance
```
Standard Hours Produced = Units × Cycle Time
Performance = (Standard Hours / Runtime) × 100%
```

## 📚 SQL vs Python

### SQL (Database Triggers)
```sql
-- Efficiency: Uses shift.start_time and shift.end_time
CALL sp_calculate_efficiency(entry_id);

-- Performance: Uses production_entry.run_time_hours
CALL sp_calculate_performance(entry_id);
```

### Python (Backend API)
```python
from backend.calculations import calculate_efficiency, calculate_performance

# Efficiency
efficiency = calculate_efficiency(
    units_produced=1000,
    ideal_cycle_time=0.01,
    employees_assigned=5,
    shift_hours=8.0  # From shift definition
)

# Performance
performance = calculate_performance(
    units_produced=1000,
    ideal_cycle_time=0.01,
    run_time_hours=6.0  # From production_entry
)
```

## ⚠️ Common Mistakes

### ❌ Mistake 1: Using Runtime for Efficiency
```python
# WRONG!
efficiency = (units * cycle_time) / (employees * runtime)
#                                                  ↑
#                                          Should be shift_hours
```

### ❌ Mistake 2: Including Employees in Performance
```python
# WRONG!
performance = (units * cycle_time) / (employees * runtime)
#                                      ↑
#                              Performance doesn't use employees
```

### ❌ Mistake 3: Confusing the Two
```python
# WRONG!
efficiency_value = calculate_performance(...)  # Mixed up functions
```

## 🎓 Remember

**Efficiency = Workforce** (uses scheduled hours)
**Performance = Machine** (uses runtime)

When in doubt:
- **Employee count in denominator?** → It's Efficiency
- **Only runtime in denominator?** → It's Performance

---

**See Also:**
- `/docs/EFFICIENCY_FORMULA_FIX.md` - Detailed technical documentation
- `/docs/EFFICIENCY_FIX_SUMMARY.md` - Fix summary and migration guide
- `/backend/calculations/efficiency.py` - Implementation code
- `/tests/test_efficiency_calculation.py` - Test suite
