# ADR 003: CRUD Organization Pattern

## Status
Accepted

## Date
2025-02-01

## Context

Large CRUD files (400-600+ lines) were becoming difficult to:
- Navigate and understand
- Test in isolation
- Maintain and extend

Files needing reorganization:
- `production.py` (489 LOC)
- `saved_filter.py` (639 LOC)
- `workflow.py` (590 LOC)
- `floating_pool.py` (583 LOC)
- `hold.py` (427 LOC)
- `employee.py` (412 LOC)

## Decision

Split large CRUD files into **subdirectory modules** with backward-compatible re-exports.

### Module Structure

```
crud/production/
  __init__.py      # Re-exports all functions
  core.py          # create, get, update, delete
  queries.py       # list, filter, search
  batch.py         # bulk operations
  kpi.py           # KPI-related calculations
```

### Naming Convention

| Module | Purpose |
|--------|---------|
| `core.py` | Basic CRUD (create, get, update, delete) |
| `queries.py` | List/filter operations |
| `batch.py` | Bulk operations |
| `kpi.py` / `calculations.py` | Domain calculations |
| `analytics.py` | Reporting queries |
| `assignments.py` | Assignment operations |
| `duration.py` | Duration/time calculations |
| `aging.py` | Aging calculations |

### Backward Compatibility

The `__init__.py` re-exports all functions:
```python
# crud/production/__init__.py
from backend.crud.production.core import create_production_entry
from backend.crud.production.queries import get_production_entries
# ... all exports

__all__ = ['create_production_entry', 'get_production_entries', ...]
```

Existing imports continue to work:
```python
from backend.crud.production import create_production_entry  # Still works!
```

## Modules Created

| Original | Split Into |
|----------|-----------|
| `production.py` | `core.py`, `queries.py`, `batch.py`, `kpi.py` |
| `saved_filter.py` | `filters.py`, `history.py`, `utilities.py` |
| `workflow.py` | `transition_log.py`, `configuration.py`, `operations.py`, `analytics.py` |
| `floating_pool.py` | `core.py`, `assignments.py`, `queries.py` |
| `hold.py` | `core.py`, `queries.py`, `duration.py`, `aging.py` |
| `employee.py` | `core.py`, `floating_pool.py`, `client_assignment.py` |

## Consequences

### Positive
- Smaller, focused files (under 200 LOC each)
- Easier to navigate and understand
- Better separation of concerns
- Easier to test individual modules
- No breaking changes to existing code

### Negative
- More files to manage
- Need to maintain `__init__.py` exports
- Slightly more complex directory structure

## Related
- ADR 001: Service Layer Pattern
- ADR 002: Domain Events
