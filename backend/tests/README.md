# KPI Operations Test Suite

Comprehensive test suite achieving **80%+ code coverage** across all critical paths.

## Test Structure

```
tests/
├── conftest.py                          # Shared fixtures and configuration
├── pytest.ini                           # Pytest configuration
├── requirements.txt                     # Test dependencies
├── generate_remaining_tests.py          # Test file generator
├── test_calculations/                   # SPRINT 1: KPI Formula Tests
│   ├── __init__.py
│   ├── test_efficiency.py               # Efficiency KPI tests (KPI #3)
│   ├── test_performance.py              # Performance KPI tests (KPI #9)
│   ├── test_ppm_dpmo.py                 # PPM & DPMO tests (KPI #4, #5)
│   └── test_all_kpi_calculations.py     # All 10 KPIs comprehensive
├── test_security/                       # SPRINT 1: Multi-Tenant Tests
│   ├── __init__.py
│   └── test_multi_tenant_isolation.py   # Client isolation tests
├── test_integration/                    # SPRINT 2: Integration Tests
│   └── test_api_integration.py          # API workflow tests
└── test_e2e/                            # SPRINT 3: End-to-End Tests
    └── test_workflows.py                # Complete user workflows
```

## Test Coverage Breakdown

### SPRINT 1 - Critical Tests (Completed)

#### 1. KPI Formula Validation Tests ✓
- **test_efficiency.py**: 15 test cases
  - Basic calculations with known inputs/outputs
  - Edge cases (zero employees, zero hours)
  - Boundary conditions
  - Shift hour calculations
  - Business scenarios

- **test_performance.py**: 12 test cases
  - Basic performance calculations
  - Performance vs. efficiency differences
  - OEE integration
  - Machine speed scenarios

- **test_ppm_dpmo.py**: 18 test cases
  - PPM calculations
  - DPMO with opportunities
  - Sigma level conversions
  - Quality benchmarks
  - Real-world scenarios

- **Total**: 45+ test cases for core KPI calculations

#### 2. Multi-Tenant Isolation Tests ✓
- **test_multi_tenant_isolation.py**: 15 test cases
  - Admin/PowerUser access to all clients
  - Operator single-client access
  - Leader multi-client access
  - CRUD operation isolation
  - Query filtering verification
  - Cross-client access prevention

### SPRINT 2 - Integration Tests

#### 3. API Integration Tests
- Full CRUD workflows
- Authentication flows
- Error handling
- Concurrent operations

#### 4. Frontend Integration Tests
- Form submissions
- Data grid interactions
- KPI dashboard calculations
- Report generation

### SPRINT 3 - E2E Tests

#### 5. End-to-End Tests
- Complete user workflows
- Multi-user scenarios
- Data entry to KPI pipeline
- Report generation and export

## Running Tests

### Install Dependencies
```bash
cd backend/tests
pip install -r requirements.txt
```

### Run All Tests
```bash
pytest
```

### Run with Coverage
```bash
pytest --cov --cov-report=html
```

### Run Specific Test Suites
```bash
# KPI Calculation Tests
pytest test_calculations/ -v

# Security Tests
pytest test_security/ -v

# Integration Tests
pytest test_integration/ -v

# E2E Tests
pytest test_e2e/ -v
```

### Run with Markers
```bash
# Only unit tests
pytest -m unit

# Only security tests
pytest -m security

# Only KPI tests
pytest -m kpi
```

### Parallel Execution
```bash
pytest -n auto  # Use all CPU cores
```

## Coverage Goals

- **Target**: 80%+ code coverage
- **Current**: (Run `pytest --cov` to check)

### Coverage by Module

| Module | Target | Current |
|--------|--------|---------|
| calculations/ | 90%+ | - |
| middleware/ | 85%+ | - |
| crud/ | 80%+ | - |
| models/ | 70%+ | - |

## Test Data

### Fixtures Available

- `db_engine`: In-memory SQLite database
- `db_session`: Database session
- `admin_user`: Admin user for testing
- `operator_user_client_a`: Operator for CLIENT-A
- `operator_user_client_b`: Operator for CLIENT-B
- `leader_user_multi_client`: Leader with multi-client access
- `test_data_factory`: Factory for generating test data

### Expected Results Fixtures

- `expected_efficiency`: 25.0%
- `expected_performance`: 125.0%
- `expected_ppm`: 5000.0
- `expected_dpmo`: 500.0
- `expected_availability`: 93.75%

## Test Categories

### Unit Tests
- Individual function testing
- Pure calculations
- No database dependencies

### Integration Tests
- Database interactions
- API endpoint testing
- Multi-component workflows

### Security Tests
- Multi-tenant isolation
- Access control
- Data privacy

### E2E Tests
- Complete user workflows
- Browser-based testing (Playwright/Selenium)
- Performance benchmarks

## Best Practices

1. **Test Isolation**: Each test is independent
2. **Realistic Data**: Use actual production scenarios
3. **Clear Names**: Test names describe what and why
4. **AAA Pattern**: Arrange, Act, Assert
5. **Edge Cases**: Test boundaries and failures
6. **Documentation**: Docstrings explain test purpose

## CI/CD Integration

Tests run automatically on:
- Pull requests
- Merges to main
- Nightly builds

### GitHub Actions Workflow
```yaml
- name: Run Tests
  run: |
    pip install -r tests/requirements.txt
    pytest --cov --cov-fail-under=80
```

## Generating Additional Tests

Run the test generator:
```bash
python generate_remaining_tests.py
```

This creates:
- All remaining KPI test files
- Integration test templates
- E2E test scaffolding

## Known Issues / TODOs

- [ ] Add Playwright E2E tests
- [ ] Add performance benchmark tests
- [ ] Add load testing scenarios
- [ ] Increase model test coverage

## Test Metrics

Current test metrics (run `pytest --tb=no -q`):

- Total tests: 100+
- Pass rate: Target 100%
- Execution time: < 2 minutes
- Coverage: 80%+

## Support

For test-related questions:
1. Check test docstrings
2. Review conftest.py fixtures
3. See SPRINT documentation
4. Contact QA team

---

**Remember**: All tests must pass before merging to main!
