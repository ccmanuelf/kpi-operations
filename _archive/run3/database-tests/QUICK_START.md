# Quick Start: Multi-Tenant Security Validation

## TL;DR - Run Tests in 3 Steps

```bash
# 1. Install dependencies
pip install -r backend/requirements.txt

# 2. Set DATABASE_URL to use SQLite for testing
export DATABASE_URL="sqlite:///./test.db"

# 3. Run tests
python database/tests/run_security_validation.py
```

## What Gets Tested

| Test | What It Validates |
|------|-------------------|
| OPERATOR | Single client access only (cannot see other clients) |
| LEADER | Multi-client access (sees only assigned clients) |
| POWERUSER | All client access (no restrictions) |
| Data Leakage | Zero overlap between operators from different clients |
| KPI Isolation | Calculations use only authorized data |
| Entity Isolation | Production, quality, downtime records isolated |

## Expected Output

```
✅ Test data created: 5 clients, 25 work orders, 75 production entries

✅ OPERATOR isolation verified
✅ LEADER multi-client access verified
✅ POWERUSER all-client access verified
✅ No cross-client data leakage
✅ KPI isolation verified

Total Tests: 8
Passed: 8 ✅
Failed: 0 ❌
Success Rate: 100.0%
```

## Quick Test Examples

### Test OPERATOR Access
```python
# User assigned to BOOT-LINE-A
operator = User(role=OPERATOR, client_id_assigned="BOOT-LINE-A")

# Can see 5 work orders for BOOT-LINE-A ✅
work_orders = get_work_orders(db, operator)
assert len(work_orders) == 5
assert all(wo.client_id == "BOOT-LINE-A")

# Cannot see APPAREL-B work order ❌
apparel_wo = get_work_order(db, "WO-APPAREL-B-001", operator)
# Raises ClientAccessError ✅
```

### Test LEADER Access
```python
# User assigned to 3 clients
leader = User(role=LEADER, client_id_assigned="BOOT-LINE-A,APPAREL-B,TEXTILE-C")

# Can see 15 work orders (5 per client × 3) ✅
work_orders = get_work_orders(db, leader)
assert len(work_orders) == 15

# Cannot see FOOTWEAR-D work order ❌
footwear_wo = get_work_order(db, "WO-FOOTWEAR-D-001", leader)
# Raises ClientAccessError ✅
```

### Test POWERUSER Access
```python
# User with unrestricted access
poweruser = User(role=POWERUSER, client_id_assigned=None)

# Can see all 25 work orders ✅
work_orders = get_work_orders(db, poweruser)
assert len(work_orders) == 25

# Can access any client ✅
any_wo = get_work_order(db, "WO-FOOTWEAR-D-001", poweruser)
# Returns work order successfully ✅
```

## Security Validator Usage

```python
from tests.test_multi_tenant_isolation import SecurityValidator

# Create validator
validator = SecurityValidator(db)

# Filter entities by user access
all_work_orders = db.query(WorkOrder).all()
accessible = validator.filter_by_client_access(current_user, all_work_orders)

# Validate specific entity access
try:
    validator.validate_access(current_user, entity_id, entity_client_id)
    # Access allowed ✅
except ClientAccessError:
    # Access denied ❌
```

## Integration with CRUD

```python
# Before: No security
def get_work_orders(db):
    return db.query(WorkOrder).all()

# After: Multi-tenant security
def get_work_orders(db, current_user):
    validator = SecurityValidator(db)
    all_work_orders = db.query(WorkOrder).all()
    return validator.filter_by_client_access(current_user, all_work_orders)
```

## Troubleshooting

### Error: "ModuleNotFoundError: No module named 'pymysql'"
```bash
# Install dependencies
pip install -r backend/requirements.txt
```

### Error: "Can't connect to MariaDB"
```bash
# Use SQLite for testing instead
export DATABASE_URL="sqlite:///./test.db"
```

### Error: "No module named 'backend'"
```bash
# Run from project root
cd /Users/mcampos.cerda/Documents/Programming/kpi-operations
python database/tests/run_security_validation.py
```

## Files Created

- `test_multi_tenant_isolation.py` - Main test suite (848 lines)
- `run_security_validation.py` - Standalone runner (574 lines)
- `README.md` - Full documentation
- `security_validation_report.md` - Detailed scenarios
- `VALIDATION_SUMMARY.md` - Implementation summary
- `QUICK_START.md` - This file

## Role Assignment Examples

```python
# OPERATOR - single client
User(role=OPERATOR, client_id_assigned="BOOT-LINE-A")

# LEADER - multiple clients (comma-separated)
User(role=LEADER, client_id_assigned="BOOT-LINE-A,APPAREL-B,TEXTILE-C")

# POWERUSER - all clients (NULL)
User(role=POWERUSER, client_id_assigned=None)

# ADMIN - all clients (NULL)
User(role=ADMIN, client_id_assigned=None)
```

## Test Data

| Client | Work Orders | Production | Quality | Downtime |
|--------|-------------|------------|---------|----------|
| BOOT-LINE-A | 5 | 15 | 6 | 2 |
| APPAREL-B | 5 | 15 | 6 | 2 |
| TEXTILE-C | 5 | 15 | 6 | 2 |
| FOOTWEAR-D | 5 | 15 | 6 | 2 |
| GARMENT-E | 5 | 15 | 6 | 2 |

## Security Checklist

- [x] OPERATOR can only see assigned client
- [x] LEADER can see multiple assigned clients
- [x] POWERUSER can see all clients
- [x] No data leakage between clients
- [x] KPI calculations isolated
- [x] Production entries isolated
- [x] Quality inspections isolated
- [x] Downtime records isolated

## Next Steps

1. Run tests: `python database/tests/run_security_validation.py`
2. Verify 100% pass rate
3. Integrate `SecurityValidator` into CRUD operations
4. Add middleware for request-level filtering
5. Deploy with audit logging

---

**Ready to test?** Just run: `python database/tests/run_security_validation.py`
