# ADR-001: Schema Naming Standards

**Date:** 2025-01-29
**Status:** Accepted
**Context:** Technical debt remediation - duplicate schemas and inconsistent naming

## Context

The codebase had accumulated significant technical debt related to SQLAlchemy schema definitions:

1. **6 pairs of duplicate schema files** - e.g., both `production.py` and `production_entry.py` existed
2. **Inconsistent field naming** - `work_order_id` vs `work_order_number`, `entry_id` vs `production_entry_id`
3. **Dead imports** - Routes and calculations importing non-existent schema files
4. **Database mismatch** - Dead schema files pointed to non-existent tables (lowercase) while actual tables are UPPERCASE

This caused:
- 108 skipped tests due to "unavailable modules" or "known schema issues"
- Empty dashboard despite seeded database (user client_id mismatch)
- Import errors and runtime failures

## Decision

### 1. Canonical Schema Files

Use the `*_entry.py` naming pattern as the canonical source for all entry-type schemas:

| Canonical File | Table Name | Purpose |
|---------------|------------|---------|
| `production_entry.py` | PRODUCTION_ENTRY | Production data |
| `quality_entry.py` | QUALITY_ENTRY | Quality inspections |
| `attendance_entry.py` | ATTENDANCE_ENTRY | Attendance records |
| `downtime_entry.py` | DOWNTIME_ENTRY | Downtime events |
| `hold_entry.py` | HOLD_ENTRY | WIP holds |

### 2. Deleted Dead Schema Files

The following files were removed as they pointed to non-existent tables:
- `schemas/production.py` (pointed to "production_entry" - wrong case)
- `schemas/attendance.py` (pointed to "attendance_records" - doesn't exist)
- `schemas/quality.py` (pointed to "quality_inspections" - doesn't exist)
- `schemas/downtime.py` (pointed to "downtime_events" - doesn't exist)
- `schemas/hold.py` (pointed to "wip_holds" - doesn't exist)

### 3. Field Naming Standards

| Standard | Format | Example |
|----------|--------|---------|
| Primary keys | `{entity}_id` | `production_entry_id`, `quality_entry_id` |
| Foreign keys | `{referenced_entity}_id` | `work_order_id`, `client_id` |
| Timestamps | `{action}_at` | `created_at`, `updated_at` |
| Flags | `is_{state}` | `is_active`, `is_deleted` |

### 4. Import Patterns

Always import from canonical schema files:

```python
# Correct
from backend.schemas.quality_entry import QualityEntry
from backend.schemas.downtime_entry import DowntimeEntry

# Wrong (these files no longer exist)
from backend.schemas.quality import QualityInspection  # DELETED
from backend.schemas.downtime import DowntimeEvent      # DELETED
```

### 5. Route Order Convention

For FastAPI routes, specific paths must be defined BEFORE parameterized paths:

```python
# Correct order
@router.get("/by-date-range")     # Specific path first
@router.get("/by-employee/{id}")  # Specific path with param
@router.get("/{id}")              # Generic parameterized LAST

# Wrong order (causes routing bugs)
@router.get("/{id}")              # This catches everything!
@router.get("/by-date-range")     # Never reached
```

## Consequences

### Positive
- Reduced skipped tests from 108 to 23
- All 3436 tests now pass
- Clear, predictable import paths
- Single source of truth for each schema
- Dashboard now shows data correctly

### Negative
- One-time migration effort to update imports
- Need to maintain backward compatibility aliases in conftest.py for tests

## Compliance

All new schemas must:
1. Follow the `*_entry.py` naming pattern for entry-type data
2. Use UPPERCASE table names matching the database
3. Use consistent field naming (see standards above)
4. Be imported using the canonical path

## References

- Original issue: 108 skipped tests, empty dashboard
- Related tasks: #46, #47, #49, #50
