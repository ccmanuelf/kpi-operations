# ADR 001: Service Layer Pattern

## Status
Accepted

## Date
2025-02-01

## Context

The KPI Operations platform has grown with business logic scattered across:
- Route handlers (coupling HTTP concerns with domain logic)
- CRUD modules (mixing data access with calculations)
- Direct database queries in routes

This creates:
- Difficult-to-test code (HTTP mocking required)
- Duplicated business logic
- Tight coupling between layers

## Decision

Introduce a **Service Layer** between routes and CRUD that:
1. Orchestrates CRUD operations with business logic
2. Coordinates cross-domain operations
3. Provides a clean API for route handlers

### Service Guidelines

**Use a Service when:**
- Business logic/calculations required
- Multiple CRUD operations coordinated
- Cross-domain aggregation needed
- External integrations involved

**Direct CRUD acceptable when:**
- Simple single-entity CRUD
- No business logic or side effects

### Implementation

Services are classes with:
- Database session injected via constructor
- Methods that coordinate business operations
- Dependency injection factory functions for FastAPI

```python
class ProductionService:
    def __init__(self, db: Session):
        self.db = db
        self.kpi_service = ProductionKPIService(db)

    def create_entry(self, data, user):
        # Business logic + CRUD coordination
        return create_production_entry(self.db, data, user)

def get_production_service(db: Session = Depends(get_db)):
    return ProductionService(db)
```

### Services Created

| Service | Purpose |
|---------|---------|
| `ProductionService` | Entry management with KPI calculations |
| `QualityService` | Inspection with PPM/DPMO |
| `WorkOrderService` | Workflow state transitions |
| `HoldService` | Hold/resume workflow, duration tracking |
| `EmployeeService` | Floating pool, client assignment |
| `AttendanceService` | Shift calculations |
| `DowntimeService` | Availability calculations |

## Consequences

### Positive
- Better testability (mock services, not HTTP)
- Single source of truth for business logic
- Cleaner route handlers
- Easier to add cross-cutting concerns (logging, events)

### Negative
- Additional layer to maintain
- Slight overhead for simple operations
- Need to decide when to use service vs direct CRUD

## Related
- ADR 002: Domain Events
- ADR 003: CRUD Organization
