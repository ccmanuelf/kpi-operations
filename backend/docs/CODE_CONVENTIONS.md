# KPI Operations Code Conventions

## Directory Structure

```
backend/
├── auth/           # Authentication and JWT handling
├── cache/          # Caching layer (KPICache)
├── calculations/   # Pure calculation functions and KPI logic
├── crud/           # Database CRUD operations
├── docs/           # Documentation (this folder)
├── middleware/     # Request/response middleware
├── migrations/     # SQL migration scripts
├── models/         # Pydantic request/response models
├── routes/         # FastAPI route handlers
├── schemas/        # SQLAlchemy ORM models
├── services/       # Business logic orchestration
└── utils/          # Utility functions
```

---

## Naming Conventions

### models/ vs schemas/ (IMPORTANT)

**This project uses a non-standard convention that is intentionally maintained:**

| Directory | Purpose | Technology |
|-----------|---------|------------|
| `models/` | Pydantic request/response models | Pydantic BaseModel |
| `schemas/` | SQLAlchemy ORM database models | SQLAlchemy Base |

**Rationale**: The original codebase followed this pattern, and changing it would cause significant churn without proportional benefit. This convention is documented here for clarity.

**Examples**:

```python
# models/work_order.py (Pydantic - API contracts)
from pydantic import BaseModel

class WorkOrderCreate(BaseModel):
    style_model: str
    planned_quantity: int
    ...

class WorkOrderResponse(BaseModel):
    work_order_id: str
    status: str
    ...
```

```python
# schemas/work_order.py (SQLAlchemy - Database table)
from sqlalchemy import Column, String, Integer
from backend.database import Base

class WorkOrder(Base):
    __tablename__ = "WORK_ORDER"
    work_order_id = Column(String(50), primary_key=True)
    status = Column(String(20))
    ...
```

### Function Naming

| Pattern | Example | Purpose |
|---------|---------|---------|
| `calculate_*_pure` | `calculate_efficiency_pure()` | Pure functions, no DB access |
| `calculate_*` | `calculate_efficiency()` | DB-dependent calculations |
| `get_*` | `get_work_order()` | Retrieve single entity |
| `list_*` or `get_*s` | `list_jobs()`, `get_work_orders()` | Retrieve multiple entities |
| `create_*` | `create_work_order()` | Create new entity |
| `update_*` | `update_work_order()` | Update existing entity |
| `delete_*` | `delete_work_order()` | Delete/soft-delete entity |

### Endpoint Naming

| Method | Pattern | Example |
|--------|---------|---------|
| GET | `/api/{entities}` | `GET /api/work-orders` |
| GET | `/api/{entities}/{id}` | `GET /api/work-orders/WO-123` |
| POST | `/api/{entities}` | `POST /api/work-orders` |
| PUT | `/api/{entities}/{id}` | `PUT /api/work-orders/WO-123` |
| DELETE | `/api/{entities}/{id}` | `DELETE /api/work-orders/WO-123` |
| POST | `/api/{entities}/{id}/{action}` | `POST /api/work-orders/WO-123/approve-qc` |

---

## Code Organization

### Service Layer Pattern (Phase 1)

```
Route → Service → Calculation (Pure) → CRUD
```

**Routes**: Handle HTTP concerns only
```python
@router.get("/efficiency")
def get_efficiency(db: Session = Depends(get_db)):
    service = ProductionKPIService(db)
    return service.calculate_efficiency()
```

**Services**: Orchestrate data fetching and calculations
```python
class ProductionKPIService:
    def calculate_efficiency(self, entry):
        # 1. Fetch required data
        product = self._fetch_product(entry.product_id)
        # 2. Infer missing values
        cycle_time = self._infer_cycle_time(entry, product)
        # 3. Call pure calculation
        return calculate_efficiency_pure(...)
```

**Calculations**: Pure functions, no side effects
```python
def calculate_efficiency_pure(units, cycle_time, employees, hours) -> Decimal:
    # Pure math, no database
    return (units * cycle_time) / (employees * hours) * 100
```

### CRUD Layer

- CRUD functions handle database operations only
- No business logic in CRUD
- Client access verification happens in CRUD
- KPI calculations delegated to services

---

## Error Handling

### HTTP Status Codes

| Status | Usage |
|--------|-------|
| 200 | Success (GET, PUT, POST with return) |
| 201 | Created (POST) |
| 204 | No Content (DELETE) |
| 400 | Bad Request (validation error) |
| 401 | Unauthorized (no/invalid token) |
| 403 | Forbidden (no access to resource) |
| 404 | Not Found |
| 500 | Internal Server Error |

### Client Access Errors

```python
from backend.middleware.client_auth import verify_client_access, ClientAccessError

def get_work_order(db, work_order_id, current_user):
    work_order = db.query(WorkOrder).filter(...).first()

    if not work_order:
        raise HTTPException(404, "Work order not found")

    # Raises 403 if user can't access this client
    verify_client_access(current_user, work_order.client_id)

    return work_order
```

---

## Database Conventions

### Table Names

- ALL_CAPS with underscores
- Examples: `WORK_ORDER`, `PRODUCTION_ENTRY`, `QUALITY_ENTRY`

### Column Names

- lowercase_with_underscores
- Foreign keys: `{entity}_id` (e.g., `client_id`, `work_order_id`)
- Timestamps: `created_at`, `updated_at`
- Soft delete: `is_active` (1=active, 0=deleted)

### Indexes

- Primary keys: Automatic
- Foreign keys: Create indexes
- Frequently queried columns: Create indexes
- Multi-tenant: Always index `client_id`

---

## Security Conventions

### Multi-Tenant Isolation

Every database query for tenant-specific data MUST include client filtering:

```python
from backend.middleware.client_auth import build_client_filter_clause

def get_work_orders(db, current_user):
    query = db.query(WorkOrder)

    # ALWAYS apply client filter
    client_filter = build_client_filter_clause(current_user, WorkOrder.client_id)
    if client_filter is not None:
        query = query.filter(client_filter)

    return query.all()
```

### Never Hardcode Secrets

- Use environment variables for all secrets
- Use `backend/config.py` settings object
- Never commit `.env` files

---

## Testing Conventions

### Pure Function Tests

```python
# tests/calculations/test_efficiency.py
from backend.calculations.efficiency import calculate_efficiency_pure
from decimal import Decimal

def test_efficiency_calculation():
    result = calculate_efficiency_pure(
        units_produced=100,
        ideal_cycle_time=Decimal("0.1"),
        employees_count=5,
        scheduled_hours=Decimal("8")
    )
    assert result == Decimal("25.00")
```

### Integration Tests

```python
# tests/integration/test_production_api.py
def test_create_production_entry(client, auth_headers, sample_data):
    response = client.post(
        "/api/production-entries",
        json=sample_data,
        headers=auth_headers
    )
    assert response.status_code == 201
```

---

## Documentation Conventions

### Docstrings

Use Google-style docstrings:

```python
def calculate_efficiency(db: Session, entry: ProductionEntry) -> EfficiencyResult:
    """
    Calculate efficiency for a production entry.

    Args:
        db: Database session
        entry: Production entry to calculate for

    Returns:
        EfficiencyResult with percentage and metadata

    Raises:
        ValueError: If entry has invalid data

    Example:
        >>> result = calculate_efficiency(db, entry)
        >>> print(result.efficiency_percentage)
        92.5
    """
```

### Phase Comments

When adding new functionality, include phase reference:

```python
# Phase 4: Job-level KPI tracking
@router.get("/{job_id}/efficiency")
def get_job_efficiency(job_id: str):
    ...
```

---

## Version Control

### Commit Messages

```
feat: Add job-level efficiency endpoint
fix: Correct PPM calculation for zero inspections
refactor: Extract pure calculation functions
docs: Add KPI formulas documentation
```

### Branch Naming

```
feature/phase-1-service-layer
feature/job-level-kpis
bugfix/efficiency-calculation
docs/domain-model
```
