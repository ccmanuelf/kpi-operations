# Manufacturing KPI Platform - Test Scenarios

Comprehensive test scenarios for Phase 1 MVP validation.

## Critical Test Scenarios

### SCENARIO 1: Perfect Data - All Fields Present

**Description**: Production entry with all required and optional fields populated.

**Input**:
```python
{
    "work_order_id": "WO-2025-001",
    "client_id": "BOOT-LINE-A",
    "shift_date": "2025-12-15",
    "shift_type": "SHIFT_1ST",
    "units_produced": 100,
    "units_defective": 2,
    "run_time_hours": 8.5,
    "employees_assigned": 10,
    "ideal_cycle_time": 0.25  # From work order
}
```

**Expected KPI Results**:
- **Efficiency**:
  - Hours Produced = 100 × 0.25 = 25.0
  - Hours Available = 10 × 9 = 90.0
  - Efficiency = 25.0 / 90.0 = **27.78%**
  - Estimated = False

- **Performance**:
  - Ideal Hours = 25.0
  - Run Time = 8.5
  - Performance = 25.0 / 8.5 = **294.12%**
  - Estimated = False

**Test Coverage**:
- `test_efficiency_calculation_standard_case`
- `test_performance_calculation_standard_case`

---

### SCENARIO 2: Missing ideal_cycle_time (Inference Engine)

**Description**: Work order missing ideal_cycle_time, system must infer from client history.

**Input**:
```python
{
    "work_order_id": "WO-2025-002",
    "client_id": "BOOT-LINE-A",
    "shift_date": "2025-12-15",
    "shift_type": "SHIFT_1ST",
    "units_produced": 100,
    "run_time_hours": 8.5,
    "employees_assigned": 10,
    "ideal_cycle_time": None  # MISSING - needs inference
}
```

**Inference Logic**:
1. Check client/style historical average → 0.28 hr
2. If not available, use shift/line standard
3. If not available, use industry default (0.25 hr)
4. Flag as "ESTIMATED"

**Expected KPI Results**:
- **Efficiency**:
  - Hours Produced = 100 × 0.28 = 28.0
  - Hours Available = 90.0
  - Efficiency = **31.11%**
  - Estimated = **True**
  - Inference Method = "client_style_average"
  - Confidence Score = 0.85

**Test Coverage**:
- `test_efficiency_missing_ideal_cycle_time_client_average`
- `test_performance_missing_ideal_cycle_time`

---

### SCENARIO 3: Missing employees_assigned (Use Shift Default)

**Description**: employees_assigned field NULL, use shift-specific default.

**Input**:
```python
{
    "work_order_id": "WO-2025-003",
    "shift_date": "2025-12-15",
    "shift_type": "SHIFT_1ST",  # Default: 10 employees
    "units_produced": 100,
    "ideal_cycle_time": 0.25,
    "employees_assigned": None  # MISSING
}
```

**Inference Logic**:
- SHIFT_1ST → Default 10 employees
- SHIFT_2ND → Default 8 employees
- SAT_OT/SUN_OT → Default 6 employees

**Expected KPI Results**:
- **Efficiency**:
  - Hours Produced = 25.0
  - Hours Available = 10 (default) × 9 = 90.0
  - Efficiency = **27.78%**
  - Estimated = **True**
  - Inference Method = "shift_default_employees"

**Test Coverage**:
- `test_efficiency_missing_employees_assigned_shift_default`

---

### SCENARIO 4: CSV Upload - 247 Rows (235 Valid, 12 Errors)

**Description**: User uploads CSV with 247 production entries, 12 have validation errors.

**Input**: CSV file with errors:
- Row 45: Invalid date format ("12/15/2025" instead of "2025-12-15")
- Row 89: Negative units_produced (-5)
- Row 156: Unknown work_order_id ("WO-XXXX")
- Row 203: Invalid shift_type ("INVALID_SHIFT")
- Rows 220, 225, 230, 235, 238, 240, 243, 246: Missing required field

**Expected Validation Result**:
```json
{
    "total_rows": 247,
    "valid_rows": 235,
    "error_rows": 12,
    "errors": [
        {"row": 45, "error": "Invalid date format (use YYYY-MM-DD)"},
        {"row": 89, "error": "Negative units produced (-5)"},
        {"row": 156, "error": "Unknown work order WO-XXXX"},
        {"row": 203, "error": "Invalid shift_type INVALID_SHIFT"},
        ...
    ],
    "allow_partial_import": true
}
```

**User Workflow**:
1. System shows: "Found 247 rows. 235 valid, 12 errors"
2. Display error preview (first 5 errors)
3. Offer [DOWNLOAD ERRORS] button
4. Offer [PROCEED WITH 235] button
5. If user confirms → Read-back dialog
6. If user confirms read-back → Save 235 valid entries

**Expected Database State**:
- 235 production entries saved
- 12 error rows logged for download
- No partial/incomplete records

**Test Coverage**:
- `test_csv_upload_partial_errors_247_scenario`
- `test_csv_batch_import_partial_allowed`
- `test_e2e_csv_upload_to_kpi_report`

---

### SCENARIO 5: Client Isolation - Multi-Tenant Security

**Description**: Ensure CLIENT-A cannot access CLIENT-B data in any scenario.

**Setup**:
```python
# CLIENT-A data
create_production_entry(client_id="CLIENT-A", units_produced=100)

# CLIENT-B data
create_production_entry(client_id="CLIENT-B", units_produced=500)
```

**Test Cases**:

**5.1: Query Isolation**
```python
# CLIENT-A queries production
results = get_production_entries(client_id="CLIENT-A")

# Expected:
assert len(results) == 1
assert all(e.client_id == "CLIENT-A" for e in results)
# CLIENT-B entry NOT in results
```

**5.2: KPI Isolation**
```python
# CLIENT-A queries efficiency
kpi = calculate_efficiency(client_id="CLIENT-A", days=30)

# Expected:
assert kpi["total_units"] == 100  # NOT 600 (100 + 500)
```

**5.3: Direct ID Access Blocked**
```python
# CLIENT-A knows CLIENT-B's production_entry_id
entry = get_production_entry_by_id(
    production_entry_id=client_b_entry_id,
    requesting_client_id="CLIENT-A"
)

# Expected:
assert entry is None  # Access denied
```

**Test Coverage**:
- `test_client_a_cannot_see_client_b_production`
- `test_client_cannot_access_by_production_id_other_client`
- `test_e2e_client_a_cannot_query_client_b_kpis`

---

### SCENARIO 6: Zero Production (Downtime Day)

**Description**: Shift with zero units produced (equipment failure, no materials).

**Input**:
```python
{
    "shift_date": "2025-12-15",
    "shift_type": "SHIFT_1ST",
    "units_produced": 0,  # Downtime
    "run_time_hours": 8.0,
    "employees_assigned": 10
}
```

**Expected KPI Results**:
- **Efficiency**:
  - Hours Produced = 0
  - Efficiency = **0.0%**
  - Flag for Review = True

- **Performance**:
  - Performance = **0.0%**

**Test Coverage**:
- `test_efficiency_zero_production`
- `test_performance_zero_production`

---

### SCENARIO 7: Concurrent Access - Multiple Clients

**Description**: CLIENT-A and CLIENT-B upload data simultaneously.

**Workflow**:
```python
# Thread 1: CLIENT-A uploads 100 entries
def upload_client_a():
    csv_a = create_csv(client="CLIENT-A", rows=100)
    api_client_a.post("/api/production/upload-csv", files=csv_a)

# Thread 2: CLIENT-B uploads 150 entries
def upload_client_b():
    csv_b = create_csv(client="CLIENT-B", rows=150)
    api_client_b.post("/api/production/upload-csv", files=csv_b)

# Execute concurrently
threads = [Thread(target=upload_client_a), Thread(target=upload_client_b)]
for t in threads: t.start()
for t in threads: t.join()
```

**Expected Result**:
- CLIENT-A: 100 entries saved (client_id="CLIENT-A")
- CLIENT-B: 150 entries saved (client_id="CLIENT-B")
- No cross-contamination
- No race conditions

**Test Coverage**:
- `test_e2e_two_clients_concurrent_uploads`
- `test_concurrent_queries_no_leakage`

---

### SCENARIO 8: Performance at Scale (1000+ Records)

**Description**: Query and report generation with 1000+ production entries.

**Setup**:
```python
# Create 1000 production entries
for i in range(1000):
    create_production_entry(
        client_id="BOOT-LINE-A",
        shift_date=date(2025, 12, 1) + timedelta(days=i % 90),
        units_produced=100
    )
```

**Test Cases**:

**8.1: Query Performance (< 2 seconds)**
```python
start = time.time()
results = api_client.get(
    "/api/production/BOOT-LINE-A?date_from=2025-10-01&date_to=2025-12-31"
)
duration = time.time() - start

assert duration < 2.0
assert len(results.json()["entries"]) == 1000
```

**8.2: PDF Generation (< 10 seconds)**
```python
start = time.time()
response = api_client.get(
    "/api/reports/pdf/daily/BOOT-LINE-A/2025-12-15"
)
duration = time.time() - start

assert duration < 10.0
assert response.headers["Content-Type"] == "application/pdf"
```

**Test Coverage**:
- `test_e2e_1000_records_query_performance`
- `test_e2e_pdf_generation_performance`

---

### SCENARIO 9: Authentication & Authorization

**Description**: Test all 4 user roles and their permissions.

**Roles**:
- **OPERATOR_DATAENTRY**: Can enter data for assigned client only
- **LEADER_DATACONFIG**: Can configure + enter data for assigned client
- **POWERUSER**: Can view all clients (read-only)
- **ADMIN**: Full system access

**Test Cases**:

**9.1: Operator Can Enter Own Client Data**
```python
# OPERATOR_DATAENTRY assigned to CLIENT-A
response = api_client.post(
    "/api/production/manual",
    json={"client_id": "CLIENT-A", ...},
    headers={"Authorization": f"Bearer {operator_token}"}
)

assert response.status_code == 201  # Success
```

**9.2: Operator Cannot Access Other Client**
```python
# Try to enter data for CLIENT-B
response = api_client.post(
    "/api/production/manual",
    json={"client_id": "CLIENT-B", ...},
    headers={"Authorization": f"Bearer {operator_token}"}
)

assert response.status_code == 403  # Forbidden
```

**9.3: PowerUser Read-Only Access**
```python
# PowerUser can view all clients
response = api_client.get(
    "/api/kpi/all-clients",
    headers={"Authorization": f"Bearer {poweruser_token}"}
)

assert response.status_code == 200
assert len(response.json()["clients"]) > 1

# But cannot modify
response = api_client.post(
    "/api/production/manual",
    json={...},
    headers={"Authorization": f"Bearer {poweruser_token}"}
)

assert response.status_code == 403  # Forbidden
```

**Test Coverage**:
- `test_operator_can_enter_data_own_client`
- `test_operator_cannot_access_other_client`
- `test_poweruser_can_view_all_clients`
- `test_poweruser_cannot_modify_data`

---

### SCENARIO 10: Read-Back Verification Workflow

**Description**: Mandatory read-back confirmation before saving data.

**Workflow**:
1. User enters 5 production entries via grid
2. User clicks [SUBMIT BATCH]
3. Read-back dialog shows:
   - "Confirm these 5 production entries for BOOT-LINE-A on 2025-12-15 SHIFT_1ST?"
   - List of all 5 entries with key details
   - Total statistics (total units, defects, run hours)
4. User clicks [CONFIRM ALL]
5. Data saved to database

**Expected Behavior**:
- Read-back dialog MUST appear (cannot skip)
- User can [EDIT] individual entries
- User can [CANCEL] entire batch
- Only after [CONFIRM] is data saved

**Test Coverage**:
- `test_e2e_manual_entry_to_readback_save`
- `test_csv_upload_readback_summary`
- `test_readback_confirm_then_save`

---

## Test Execution

Run all scenarios:
```bash
./tests/run_tests.sh
```

Run specific scenario:
```bash
pytest tests/backend/test_efficiency_calculation.py::TestEfficiencyCalculationPerfectData::test_efficiency_calculation_standard_case -v
```

Generate scenario report:
```bash
pytest --html=tests/scenario_report.html
```

---

**Total Scenarios**: 10 critical + 50+ edge cases
**Total Tests**: 150+
**Coverage Target**: 90%+
