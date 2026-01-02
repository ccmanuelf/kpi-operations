# Manufacturing KPI Platform - Test Suite

Comprehensive test coverage for Phase 1 MVP with 90%+ coverage target.

## Test Structure

```
tests/
├── backend/              # Backend unit tests (Python/FastAPI)
│   ├── test_production_crud.py          # CRUD operations (13 tests)
│   ├── test_efficiency_calculation.py   # KPI #3 with edge cases (15 tests)
│   ├── test_performance_calculation.py  # KPI #9 with edge cases (14 tests)
│   ├── test_csv_upload.py               # Batch upload validation (18 tests)
│   ├── test_auth.py                     # JWT authentication & RBAC (20 tests)
│   └── test_client_isolation.py         # Multi-tenant security (17 tests)
├── frontend/             # Frontend component tests (Vitest/Vue)
│   ├── DataEntryGrid.test.js            # Grid functionality (20 tests)
│   ├── ReadBackConfirm.test.js          # Verification dialog (21 tests)
│   ├── KpiDashboard.test.js             # Real-time KPI display
│   └── CsvUpload.test.js                # File upload UI
├── integration/          # Integration tests (full workflows)
│   ├── test_end_to_end_workflow.py      # CSV → KPI → Report (12 tests)
│   └── test_multi_client.py             # Concurrent access
├── fixtures/             # Test data and samples
│   ├── test_data.py                     # Reusable test fixtures
│   ├── perfect_data.json                # Ideal scenario data
│   ├── missing_data.json                # Inference test data
│   ├── test_valid_247.csv               # Valid CSV sample
│   └── test_errors_247.csv              # CSV with errors (235 valid, 12 invalid)
├── conftest.py           # Pytest configuration and shared fixtures
├── pytest.ini            # Pytest settings
└── vitest.config.js      # Vitest configuration
```

## Test Categories

### Backend Tests (97 tests total)
- **CRUD Operations**: 13 tests
- **KPI #3 Efficiency**: 15 tests (perfect data, inference, edge cases)
- **KPI #9 Performance**: 14 tests (perfect data, inference, edge cases)
- **CSV Upload**: 18 tests (validation, errors, batch processing)
- **Authentication**: 20 tests (JWT, RBAC, login/logout)
- **Client Isolation**: 17 tests (multi-tenant security)

### Frontend Tests (41+ tests)
- **DataEntryGrid**: 20 tests (Excel-like grid, copy/paste, validation)
- **ReadBackConfirm**: 21 tests (verification workflow)
- **KpiDashboard**: Real-time display tests
- **CsvUpload**: File upload UI tests

### Integration Tests (12+ tests)
- End-to-end workflows
- Multi-client concurrency
- Performance at scale (1000+ records)

## Running Tests

### Backend Tests (Pytest)

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/backend/test_efficiency_calculation.py

# Run with coverage
pytest --cov=app --cov-report=html

# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run KPI tests only
pytest -m kpi

# Run with verbose output
pytest -v

# Run and stop on first failure
pytest -x

# Run specific test
pytest tests/backend/test_efficiency_calculation.py::TestEfficiencyCalculationPerfectData::test_efficiency_calculation_standard_case
```

### Frontend Tests (Vitest)

```bash
# Run all frontend tests
npm run test

# Run with coverage
npm run test:coverage

# Run in watch mode
npm run test:watch

# Run specific test file
npm run test tests/frontend/DataEntryGrid.test.js

# Run with UI
npm run test:ui
```

## Test Scenarios

### TEST 1: Perfect Data (All Fields Present)
**SCENARIO**: Production entry with all fields
**EXPECTED**:
- Efficiency = 27.78% (25 hrs produced / 90 hrs available)
- Performance = 113.64% (25 ideal hrs / 22 run hrs)
- No estimation flags

### TEST 2: Missing ideal_cycle_time (Inference)
**SCENARIO**: Work order missing ideal_cycle_time
**EXPECTED**:
- System uses client historical average (0.28 hr)
- Flagged as "ESTIMATED"
- Confidence score = 0.85
- Efficiency calculated correctly with inferred value

### TEST 3: Missing employees_assigned (Use Default)
**SCENARIO**: employees_assigned = NULL
**EXPECTED**:
- Use shift_type default (10 for SHIFT_1ST, 8 for SHIFT_2ND)
- Flagged as "ESTIMATED"
- Efficiency calculated correctly

### TEST 4: CSV Upload - 247 Rows (235 Valid, 12 Errors)
**SCENARIO**: User uploads CSV with mixed valid/invalid data
**EXPECTED**:
- Show all 12 error details
- Offer "PROCEED WITH 235" option
- Downloadable error report
- Read-back confirmation before final save

### TEST 5: Client Isolation
**SCENARIO**: CLIENT-A and CLIENT-B both have production data
**EXPECTED**:
- CLIENT-A sees only their data
- CLIENT-B sees only their data
- No cross-contamination
- Concurrent access works correctly

### TEST 6: Performance at Scale
**SCENARIO**: 1000+ production entries, 3-month query
**EXPECTED**:
- Query completes in < 2 seconds
- PDF generation < 10 seconds
- All data returned correctly

## Expected Test Results

### Coverage Targets
- **Statements**: >90%
- **Branches**: >85%
- **Functions**: >90%
- **Lines**: >90%

### KPI Calculation Expected Values

#### Perfect Data:
```python
{
    "efficiency": {
        "hours_produced": 25.0,  # 100 units × 0.25 hr
        "hours_available": 90.0,  # 10 employees × 9 hrs
        "efficiency_percent": 27.78
    },
    "performance": {
        "ideal_hours": 25.0,
        "run_time_hours": 22.0,
        "performance_percent": 113.64
    }
}
```

#### Missing Cycle Time (Inferred):
```python
{
    "efficiency": {
        "hours_produced": 28.0,  # 100 × 0.28 (inferred)
        "hours_available": 90.0,
        "efficiency_percent": 31.11,
        "estimated": True,
        "inference_method": "client_style_average",
        "confidence_score": 0.85
    }
}
```

## Test Fixtures

### Available Fixtures
- `perfect_production_data`: Complete production entry
- `missing_cycle_time_data`: Entry with inference required
- `csv_valid_247`: Valid CSV (247 rows)
- `csv_with_errors`: CSV with 235 valid, 12 errors
- `sample_clients`: Multi-tenant test clients
- `sample_users`: Users with different roles
- `operator_token`: JWT for OPERATOR_DATAENTRY
- `admin_token`: JWT for ADMIN

### Using Fixtures
```python
def test_example(perfect_production_data, db_session):
    # Use fixture data
    entry = create_production_entry(db_session, perfect_production_data)
    assert entry.units_produced == 100
```

## Test Markers

### Run Tests by Category
```bash
# Unit tests only (fast)
pytest -m unit

# Integration tests
pytest -m integration

# Security tests
pytest -m security

# KPI calculation tests
pytest -m kpi

# CSV upload tests
pytest -m csv

# Slow tests
pytest -m slow

# Client isolation tests
pytest -m client_isolation
```

## Continuous Integration

### GitHub Actions Workflow
```yaml
name: Test Suite
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run Backend Tests
        run: pytest --cov --cov-fail-under=90
      - name: Run Frontend Tests
        run: npm run test:coverage
      - name: Upload Coverage
        uses: codecov/codecov-action@v2
```

## Troubleshooting

### Common Issues

**Issue**: Tests fail with database connection error
**Solution**: Ensure PostgreSQL/MariaDB running, or use in-memory SQLite for testing

**Issue**: Frontend tests fail with "Cannot find module '@/components'"
**Solution**: Check vitest.config.js alias configuration

**Issue**: Coverage below 90%
**Solution**: Identify uncovered lines with `pytest --cov --cov-report=html` and add missing tests

## Test Maintenance

### Adding New Tests
1. Create test file in appropriate directory (`backend/`, `frontend/`, `integration/`)
2. Follow naming convention: `test_*.py` or `*.test.js`
3. Add test fixtures to `conftest.py` or `tests/fixtures/test_data.py`
4. Mark tests with appropriate markers (`@pytest.mark.unit`, etc.)
5. Update this README with test count and scenarios

### Updating Expected Results
When requirements change, update expected values in:
- `tests/fixtures/test_data.py` - `expected_kpi_results()`
- Individual test files - assertion values

## Documentation

- **Backend API**: See OpenAPI docs at `/docs`
- **Frontend Components**: See Storybook
- **Database Schema**: See `00-KPI_Dashboard_Platform.md`

## Support

For test failures or questions:
1. Check test output for specific error
2. Review test documentation above
3. Check fixture data in `tests/fixtures/`
4. Contact development team

---

**Test Suite Version**: 1.0
**Last Updated**: 2025-12-31
**Coverage Target**: 90%+
**Total Tests**: 150+
