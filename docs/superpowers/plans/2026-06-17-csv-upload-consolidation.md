# CSV-upload endpoint consolidation (C2) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse the 11 near-identical CSV/XLSX upload endpoints in `backend/endpoints/csv_upload.py` (1181 lines) onto one shared `process_csv_upload()` helper, behavior-preserving, after first adding characterization tests for the 9 untested endpoints; normalize two inline auth checks to declarative dependencies.

**Architecture:** Thin endpoints + shared processor (spec Approach A). A new `backend/services/csv_upload_processor.py` owns the byte-identical per-row loop / counters / 3-way exception handler / `CSVUploadResponse` assembly and a `read_upload()` preamble helper. Each endpoint keeps its route/auth/docstring and reduces to `read_upload(...)` → `process_csv_upload(rows, db, user, row_mapper=_map_<entity>_row, create_fn=..., id_getter=...)`. The per-entity `_map_<entity>_row` holds the existing column-mapping/date-parsing/`verify_client_access`/schema-construction, moved verbatim.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic v2, pytest (sqlite test DB via `test_client`).

**Spec:** `docs/superpowers/specs/2026-06-17-csv-upload-consolidation-design.md`.

**Branch:** `refactor/csv-upload-consolidation` (spec committed here @ `0fe64c4`).

## Global Constraints

- **Behavior-preserving:** identical routes, success status, `CSVUploadResponse` shape + values, the 3 error strings (`"Validation error in CSV row data"`, `"Database error processing row"`, `"Data parsing error in CSV row"`), `errors[:100]`, row numbering `enumerate(rows, start=2)`, per-entity column aliases/date formats, CRUD calls, created-id values, per-row `verify_client_access` on the 8 transactional endpoints.
- **Intentional robustness changes only:** `employees` auth `get_current_active_supervisor`+inline-admin-check → `Depends(get_current_admin)`; `floating-pool` → `Depends(get_current_planner)` (admin/poweruser). Effective access identical; only the 403 detail message normalizes. Uniform `sanitize_csv_value` on every written string field.
- **Tests:** `pytest tests/` from `backend/` (no PYTHONPATH). Coverage gate ≥75% (must not drop; expected to rise). **One expected status per assert — never `assert x in [...]`** (permissive assertions are rejected).
- **Auth fixtures:** `admin_auth_headers` (admin — passes every tier; use for happy/invalid-row characterization) and `auth_headers` (self-registered ⇒ operator role ⇒ 403 on every upload endpoint; use for the 403 test). Both in `tests/conftest.py`.
- **Characterization isolates the DB:** monkeypatch the endpoint module's `create_<entity>` symbol to a stub so happy-path tests need no FK seeding — they exercise the real endpoint + mapper + processor and assert the response + that the stub received the correctly-mapped entry.
- Commit frequently. CI's 4 required checks must stay green.

### Per-entity reference table

| entity | route | auth (current → target) | schema ctor | create fn | id attr | required cols | mapping lines | tested? |
|---|---|---|---|---|---|---|---|---|
| downtime | `/api/downtime/upload/csv` | supervisor (unchanged) | `DowntimeEventCreate.from_legacy_csv` | `create_downtime_event` | `downtime_entry_id` | client_id, work_order_id\|work_order_number, shift_date\|production_date, downtime_category\|downtime_reason, duration_hours\|downtime_duration_minutes | 114–215 | yes |
| holds | `/api/holds/upload/csv` | supervisor | `WIPHoldCreate.from_legacy_csv` | `create_wip_hold` | `hold_entry_id` | client_id, work_order_id\|work_order_number | 216–316 | no |
| attendance | `/api/attendance/upload/csv` | supervisor | `AttendanceRecordCreate.from_legacy_csv` | `create_attendance_record` | `attendance_entry_id` | client_id, employee_id, shift_date\|attendance_date, scheduled_hours, status | 317–422 | no |
| coverage | `/api/coverage/upload/csv` | supervisor | `ShiftCoverageCreate(...)` inline | `create_shift_coverage` | `coverage_id` | shift_id, coverage_date, required_employees, actual_employees | 423–500 | no |
| quality | `/api/quality/upload/csv` | supervisor | `QualityInspectionCreate.from_legacy_csv` | `create_quality_inspection` | `quality_entry_id` | client_id, work_order_id\|work_order_number, shift_date\|inspection_date, units_inspected, units_passed | 501–623 | no |
| defects | `/api/defects/upload/csv` | supervisor | `DefectDetailCreate(...)` inline | `create_defect_detail` | `defect_detail_id` | defect_detail_id, quality_entry_id, client_id_fk, defect_type, defect_count | 624–705 | no |
| work-orders | `/api/work-orders/upload/csv` | supervisor | `WorkOrderCreate(...)` inline | `create_work_order` | `work_order_id` | work_order_id, client_id, style_model, planned_quantity | 706–814 | yes |
| jobs | `/api/jobs/upload/csv` | supervisor | `JobCreate(...)` inline | `create_job` | `job_id` | job_id, work_order_id, client_id_fk, operation_name, sequence_number | 815–920 | no |
| clients | `/api/clients/upload/csv` | admin (unchanged) | `ClientCreate(...)` inline | `create_client` | `client_id` | client_id, client_name | 921–1009 | no |
| employees | `/api/employees/upload/csv` | supervisor+inline-admin → **`get_current_admin`** | `EmployeeCreate(...)` inline; `create_employee(db, entry.model_dump(), user)` | `create_employee` | `employee_id` | employee_code, employee_name | 1010–1098 | no |
| floating-pool | `/api/floating-pool/upload/csv` | supervisor+inline-planner → **`get_current_planner`** | `FloatingPoolCreate(...)` inline; `create_floating_pool_entry(db, entry.model_dump(), user)` | `create_floating_pool_entry` | `pool_id` | employee_id | 1099–1181 | no |

> **`.model_dump()` adapter:** `employees` and `floating-pool` call their CRUD with `entry.model_dump()`, not the schema object. Preserve this by wiring `create_fn=lambda db, e, u: create_employee(db, e.model_dump(), u)` (and likewise for floating-pool) — the processor calls `create_fn(db, entry, user)` uniformly.

---

## Task 1: Shared processor + `read_upload` (with unit tests)

**Files:**
- Create: `backend/services/csv_upload_processor.py`
- Create: `backend/tests/test_services/test_csv_upload_processor.py` (path: `backend/tests/test_services/...` — mirror existing `tests/` layout; if `test_services/` doesn't exist, create it)

**Interfaces — Produces:**
- `read_upload(content: bytes, filename: str, sheet_name: str | None = None) -> list[dict]`
- `process_csv_upload(rows: list[dict], db, current_user, *, row_mapper, create_fn, id_getter) -> CSVUploadResponse`
- re-exports `sanitize_csv_value`, `_read_upload_file`, `_MAX_CSV_SIZE`, `_ALLOWED_EXTENSIONS` (moved from `csv_upload.py`).

- [ ] **Step 1: Write the processor + helper.**
```python
# backend/services/csv_upload_processor.py
"""Shared CSV/XLSX upload processing — one correct per-row loop for all upload endpoints."""
import csv
import io
import logging
from decimal import InvalidOperation
from typing import Any, Callable, Optional

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.orm.user import User
from backend.schemas.production import CSVUploadResponse

logger = logging.getLogger(__name__)

_CSV_INJECTION_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
_MAX_CSV_SIZE = 10 * 1024 * 1024  # 10MB
_ALLOWED_EXTENSIONS = (".csv", ".xlsx")


def sanitize_csv_value(value: str) -> str:
    """Strip CSV injection prefixes (=, +, -, @, \\t, \\r) from string values."""
    if isinstance(value, str) and value and value[0] in _CSV_INJECTION_PREFIXES:
        return "'" + value
    return value


def _read_upload_file(file_content: bytes, filename: str, sheet_name: Optional[str] = None) -> list[dict]:
    """Read uploaded file (CSV or XLSX) → list of row dicts (csv.DictReader-shaped)."""
    lower_name = (filename or "").lower()
    if lower_name.endswith(".xlsx"):
        from backend.services.xlsx_parser import parse_xlsx_to_rows
        try:
            return parse_xlsx_to_rows(file_content, sheet_name=sheet_name, fuzzy_headers=True)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid XLSX file: {exc}")
    if lower_name.endswith(".csv"):
        return list(csv.DictReader(io.StringIO(file_content.decode("utf-8"))))
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File must be a .csv or .xlsx file")


def read_upload(content: bytes, filename: str, sheet_name: Optional[str] = None) -> list[dict]:
    """Validate extension + size, then parse. Raises the same 400/413 as the legacy endpoints."""
    if not (filename or "").lower().endswith(_ALLOWED_EXTENSIONS):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File must be a .csv or .xlsx file")
    if len(content) > _MAX_CSV_SIZE:
        raise HTTPException(status_code=413, detail="File size exceeds 10MB limit")
    return _read_upload_file(content, filename, sheet_name=sheet_name)


def process_csv_upload(
    rows: list[dict],
    db: Session,
    current_user: User,
    *,
    row_mapper: Callable[[dict, User], Any],
    create_fn: Callable[[Session, Any, User], Any],
    id_getter: Callable[[Any], Any],
) -> CSVUploadResponse:
    """Run each row through row_mapper → create_fn, collecting the same counts/errors as the legacy endpoints."""
    total_rows = 0
    successful = 0
    failed = 0
    errors: list[dict] = []
    created_ids: list = []

    for row_num, row in enumerate(rows, start=2):
        total_rows += 1
        try:
            entry = row_mapper(row, current_user)
            created = create_fn(db, entry, current_user)
            created_ids.append(id_getter(created))
            successful += 1
        except ValidationError as e:
            logger.warning("CSV row %d validation failed: %s", row_num, e)
            failed += 1
            errors.append({"row": row_num, "error": "Validation error in CSV row data", "data": row})
        except SQLAlchemyError:
            logger.exception("Database error processing CSV row %d", row_num)
            failed += 1
            errors.append({"row": row_num, "error": "Database error processing row", "data": row})
        except (ValueError, TypeError, KeyError, InvalidOperation) as e:
            logger.warning("Data parsing error in CSV row %d: %s", row_num, e)
            failed += 1
            errors.append({"row": row_num, "error": "Data parsing error in CSV row", "data": row})

    return CSVUploadResponse(
        total_rows=total_rows, successful=successful, failed=failed, errors=errors[:100], created_entries=created_ids
    )
```

- [ ] **Step 2: Write unit tests covering the happy path + each exception branch + the `errors[:100]` cap.**
```python
# backend/tests/test_services/test_csv_upload_processor.py
import pytest
from pydantic import BaseModel, ValidationError
from sqlalchemy.exc import SQLAlchemyError
from backend.services.csv_upload_processor import process_csv_upload, sanitize_csv_value


class _Created:
    def __init__(self, _id): self.id = _id


def _id_getter(c): return c.id


def test_all_rows_succeed():
    rows = [{"v": "1"}, {"v": "2"}]
    res = process_csv_upload(
        rows, db=None, current_user=None,
        row_mapper=lambda row, user: row, create_fn=lambda db, e, u: _Created(e["v"]), id_getter=_id_getter,
    )
    assert res.total_rows == 2
    assert res.successful == 2
    assert res.failed == 0
    assert res.created_entries == ["1", "2"]


def test_validation_error_row_recorded_with_exact_message():
    class _M(BaseModel):
        n: int

    def mapper(row, user):
        _M(n="not-an-int")  # raises pydantic ValidationError
        return row
    res = process_csv_upload([{"a": "1"}], db=None, current_user=None,
                             row_mapper=mapper, create_fn=lambda db, e, u: _Created(1), id_getter=_id_getter)
    assert res.failed == 1
    assert res.errors[0] == {"row": 2, "error": "Validation error in CSV row data", "data": {"a": "1"}}


def test_database_error_row_recorded():
    def create(db, e, u):
        raise SQLAlchemyError("boom")
    res = process_csv_upload([{"a": "1"}], db=None, current_user=None,
                             row_mapper=lambda row, user: row, create_fn=create, id_getter=_id_getter)
    assert res.failed == 1
    assert res.errors[0]["error"] == "Database error processing row"


def test_parsing_error_row_recorded():
    def mapper(row, user):
        raise ValueError("bad date")
    res = process_csv_upload([{"a": "1"}], db=None, current_user=None,
                             row_mapper=mapper, create_fn=lambda db, e, u: _Created(1), id_getter=_id_getter)
    assert res.failed == 1
    assert res.errors[0]["error"] == "Data parsing error in CSV row"


def test_errors_capped_at_100():
    rows = [{"a": str(i)} for i in range(150)]
    res = process_csv_upload(rows, db=None, current_user=None,
                             row_mapper=lambda row, user: (_ for _ in ()).throw(ValueError("x")),
                             create_fn=lambda db, e, u: _Created(1), id_getter=_id_getter)
    assert res.failed == 150
    assert len(res.errors) == 100


def test_row_numbering_starts_at_2():
    res = process_csv_upload([{"a": "1"}], db=None, current_user=None,
                             row_mapper=lambda row, user: (_ for _ in ()).throw(ValueError("x")),
                             create_fn=lambda db, e, u: _Created(1), id_getter=_id_getter)
    assert res.errors[0]["row"] == 2


def test_sanitize_csv_value_prefixes():
    assert sanitize_csv_value("=cmd") == "'=cmd"
    assert sanitize_csv_value("safe") == "safe"
```

- [ ] **Step 3: Run.** `pytest tests/test_services/test_csv_upload_processor.py -v` → all PASS. (Run from `backend/`.)

- [ ] **Step 4: Commit.**
```bash
git add backend/services/csv_upload_processor.py backend/tests/test_services/test_csv_upload_processor.py
git commit -m "feat(csv): shared process_csv_upload + read_upload helper (C2 Task 1)"
```

---

## Task 2: Characterization test — worked pattern (holds)

Establishes the golden-master pattern the remaining endpoints follow. Run against **current** (unrefactored) `csv_upload.py` — it must PASS now.

**Files:**
- Create: `backend/tests/test_api/test_csv_upload_characterization.py`

- [ ] **Step 1: Write the holds characterization (happy + invalid-row + auth-403).**
```python
# backend/tests/test_api/test_csv_upload_characterization.py
"""Golden-master characterization of the CSV upload endpoints (pre/post C2 refactor).

Hits the REAL endpoints via TestClient. CRUD create_* is monkeypatched to a stub so
happy-path rows need no FK seeding — the real endpoint + mapper + processor still run.
"""
import io


def _csv_bytes(header: str, *rows: str) -> bytes:
    return ("\n".join([header, *rows]) + "\n").encode("utf-8")


def _files(content: bytes, name="upload.csv"):
    return {"file": (name, io.BytesIO(content), "text/csv")}


class _Created:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_holds_happy_path(test_client, admin_auth_headers, monkeypatch):
    captured = {}

    def stub(db, entry, user):
        captured["entry"] = entry
        return _Created(hold_entry_id="HOLD-1")

    monkeypatch.setattr("backend.endpoints.csv_upload.create_wip_hold", stub)
    content = _csv_bytes("client_id,work_order_number", "CLIENT-A,WO-1")
    resp = test_client.post("/api/holds/upload/csv", files=_files(content), headers=admin_auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["successful"] == 1
    assert body["failed"] == 0
    assert body["created_entries"] == ["HOLD-1"]
    assert captured["entry"] is not None  # mapper produced a schema object


def test_holds_invalid_row_recorded(test_client, admin_auth_headers, monkeypatch):
    monkeypatch.setattr("backend.endpoints.csv_upload.create_wip_hold",
                        lambda db, e, u: _Created(hold_entry_id="X"))
    # Missing required client_id → mapper raises → counted as failed (create never called)
    content = _csv_bytes("client_id,work_order_number", ",WO-1")
    resp = test_client.post("/api/holds/upload/csv", files=_files(content), headers=admin_auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["failed"] == 1
    assert body["successful"] == 0
    assert body["errors"][0]["row"] == 2


def test_holds_requires_elevated_role(test_client, auth_headers):
    # auth_headers self-registers ⇒ operator ⇒ 403 on this supervisor-tier endpoint
    content = _csv_bytes("client_id,work_order_number", "CLIENT-A,WO-1")
    resp = test_client.post("/api/holds/upload/csv", files=_files(content), headers=auth_headers)
    assert resp.status_code == 403
```

- [ ] **Step 2: Run against CURRENT code.** `pytest tests/test_api/test_csv_upload_characterization.py -v` → 3 PASS.
  - If the happy-path mapper rejects the minimal row (a required column this table missed), inspect the endpoint's mapping (holds: lines 216–316) and add the missing column to the CSV until it succeeds. Keep the row minimal-valid.

- [ ] **Step 3: Commit.**
```bash
git add backend/tests/test_api/test_csv_upload_characterization.py
git commit -m "test(csv): characterize holds upload endpoint (C2 Task 2)"
```

---

## Task 3: Characterization tests — remaining 8 untested endpoints

Apply Task 2's three-test pattern to: **attendance, coverage, quality, defects, jobs, clients, employees, floating-pool**. Use the reference table for each endpoint's route, required columns, `create_*` symbol (monkeypatch target `backend.endpoints.csv_upload.<create_fn>`), and the id attr the stub must set.

**Files:**
- Modify: `backend/tests/test_api/test_csv_upload_characterization.py`

- [ ] **Step 1: For each of the 8 endpoints, add 3 tests** (`_happy_path`, `_invalid_row_recorded`, `_requires_elevated_role`) mirroring Task 2. Per-endpoint specifics:
  - **Monkeypatch target + stub id attr** = the reference table's `create fn` / `id attr` (e.g. attendance → `create_attendance_record`, stub returns `_Created(attendance_entry_id="A-1")`).
  - **Happy CSV** = the required columns with minimal valid values (dates `YYYY-MM-DD`; ints as strings; enums per docstring — e.g. attendance `status` ∈ {Present, Absent, Late, Leave, Vacation, Medical}; defects `defect_type` e.g. `Stitching`).
  - **clients** is admin-tier — its `_requires_elevated_role` test: `auth_headers` (operator) → 403. `clients` happy/invalid still use `admin_auth_headers`.
  - **employees / floating-pool**: their CRUD is called with `entry.model_dump()` today, so the stub still just returns `_Created(employee_id=...)` / `_Created(pool_id=...)` — the monkeypatched stub replaces the whole call, so `.model_dump()` is bypassed; that's fine for characterization (the response is what's pinned). Their `_requires_elevated_role`: `auth_headers` (operator) → 403.

- [ ] **Step 2: Run the whole characterization file against CURRENT code.** `pytest tests/test_api/test_csv_upload_characterization.py -v` → all 27 PASS (9 endpoints × 3). Adjust any happy CSV that the real mapper rejects (inspect that endpoint's mapping lines) until minimal-valid.

- [ ] **Step 3: Commit.**
```bash
git add backend/tests/test_api/test_csv_upload_characterization.py
git commit -m "test(csv): characterize remaining 8 upload endpoints (C2 Task 3)"
```

---

## Task 4: Convert the 4 `from_legacy_csv` endpoints to the processor

Convert **downtime, holds, attendance, quality** (those using `<Schema>.from_legacy_csv`). Move each endpoint's per-row mapping (everything inside the row `try:` up to and including building `entry`, including the per-row `verify_client_access`) verbatim into a module-level `_map_<entity>_row(row, current_user)` that returns `entry`; replace the endpoint body with `read_upload(...)` + `process_csv_upload(...)`.

**Files:**
- Modify: `backend/endpoints/csv_upload.py` (downtime 114–215, holds 216–316, attendance 317–422, quality 501–623)

- [ ] **Step 1: Add the import** at the top of `csv_upload.py`:
```python
from backend.services.csv_upload_processor import process_csv_upload, read_upload, sanitize_csv_value
```
Remove the now-duplicated `sanitize_csv_value`/`_read_upload_file`/`_MAX_CSV_SIZE`/`_ALLOWED_EXTENSIONS` definitions from `csv_upload.py` (they live in the service now); keep `_read_upload_file` import if still referenced, else import from the service too.

- [ ] **Step 2: Worked example — downtime.** Replace lines 114–212 with:
```python
def _map_downtime_row(row: dict, current_user):
    client_id = sanitize_csv_value(row.get("client_id", ""))
    if not client_id:
        raise ValueError("client_id is required")
    verify_client_access(current_user, client_id)
    shift_date_str = row.get("shift_date") or row.get("production_date")
    if not shift_date_str:
        raise ValueError("shift_date or production_date is required")
    shift_date = datetime.strptime(shift_date_str, "%Y-%m-%d").date()
    csv_data = {
        "client_id": client_id,
        "work_order_number": sanitize_csv_value(row.get("work_order_number") or row.get("work_order_id") or ""),
        "shift_date": shift_date,
        "downtime_category": sanitize_csv_value(row.get("downtime_category") or ""),
        "downtime_reason": sanitize_csv_value(row.get("downtime_reason") or ""),
        "duration_hours": row.get("duration_hours"),
        "downtime_duration_minutes": int(row["downtime_duration_minutes"]) if row.get("downtime_duration_minutes") else None,
        "machine_id": sanitize_csv_value(row.get("machine_id") or ""),
        "equipment_code": sanitize_csv_value(row.get("equipment_code") or ""),
        "root_cause_category": sanitize_csv_value(row.get("root_cause_category") or ""),
        "corrective_action": sanitize_csv_value(row.get("corrective_action") or ""),
        "notes": sanitize_csv_value(row.get("notes") or ""),
    }
    return DowntimeEventCreate.from_legacy_csv(csv_data)


@router.post("/api/downtime/upload/csv", response_model=CSVUploadResponse)
async def upload_downtime_csv(
    file: UploadFile = File(...),
    sheet_name: Optional[str] = Query(None, description="Sheet name for XLSX files"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor),
) -> CSVUploadResponse:
    """<keep the existing docstring verbatim>"""
    rows = read_upload(await file.read(), file.filename or "", sheet_name)
    return process_csv_upload(
        rows, db, current_user,
        row_mapper=_map_downtime_row, create_fn=create_downtime_event,
        id_getter=lambda c: c.downtime_entry_id,
    )
```

- [ ] **Step 3: Repeat for holds, attendance, quality** — for each, lift its existing per-row mapping into `_map_<entity>_row` (the body is in its mapping-lines range; the `<Schema>.from_legacy_csv(csv_data)` call is the last line, returned), keep the docstring, and wire `create_fn` + `id_getter` from the reference table. Do not alter any column alias, date format, or `verify_client_access` call.

- [ ] **Step 4: Run the safety net.** From `backend/`:
```
pytest tests/test_api/test_csv_upload_characterization.py tests/test_api/test_csv_upload_comprehensive.py tests/test_endpoints/test_xlsx_upload.py tests/test_services/test_csv_upload_processor.py -v
```
Expected: all PASS (downtime/holds/attendance/quality characterization unchanged; processor + XLSX green).

- [ ] **Step 5: Commit.**
```bash
git add backend/endpoints/csv_upload.py
git commit -m "refactor(csv): route from_legacy_csv endpoints through process_csv_upload (C2 Task 4)"
```

---

## Task 5: Convert the inline-mapping endpoints

Convert **coverage, defects, work-orders, jobs, clients** (inline `<Schema>(...)` construction). Same mechanics as Task 4: lift the per-row mapping (including inner date-parse try blocks, `verify_client_access` where present) into `_map_<entity>_row` returning the constructed `entry`; wire the endpoint.

**Files:**
- Modify: `backend/endpoints/csv_upload.py` (coverage 423–500, defects 624–705, work-orders 706–814, jobs 815–920, clients 921–1009)

- [ ] **Step 1: For each endpoint**, move the existing per-row mapping verbatim into `_map_<entity>_row(row, current_user)` (an inner helper like `parse_datetime` stays nested inside the mapper), `return <Schema>(...)`. Replace the body with `read_upload(...)` + `process_csv_upload(..., row_mapper=_map_<entity>_row, create_fn=<create>, id_getter=lambda c: c.<id_attr>)` per the reference table. `clients` keeps `Depends(get_current_admin)`. Preserve every docstring.

- [ ] **Step 2: Run the safety net** (same command as Task 4 Step 4) → all PASS (coverage/defects/work-orders/jobs/clients characterization unchanged, work-orders existing tests green).

- [ ] **Step 3: Commit.**
```bash
git add backend/endpoints/csv_upload.py
git commit -m "refactor(csv): route inline-mapping endpoints through process_csv_upload (C2 Task 5)"
```

---

## Task 6: Convert employees + floating-pool with auth normalization + sanitization sweep

**Files:**
- Modify: `backend/endpoints/csv_upload.py` (employees 1010–1098, floating-pool 1099–1181)

- [ ] **Step 1: employees — normalize auth.** Change the dependency to `current_user: User = Depends(get_current_admin)` and DELETE the inline `if current_user.role != UserRole.ADMIN: raise HTTPException(403, ...)` block. Move the mapping into `_map_employees_row(row, current_user)` returning the `EmployeeCreate(...)`. Wire with the model_dump adapter:
```python
return process_csv_upload(
    rows, db, current_user,
    row_mapper=_map_employees_row,
    create_fn=lambda db_, e, u: create_employee(db_, e.model_dump(), u),
    id_getter=lambda c: c.employee_id,
)
```

- [ ] **Step 2: floating-pool — normalize auth.** Change the dependency to `Depends(get_current_planner)` and DELETE the inline `if current_user.role not in [UserRole.ADMIN, UserRole.POWERUSER]: raise HTTPException(403, ...)` block. Add the import `get_current_planner` to the `from backend.auth.jwt import ...` line. Move the mapping into `_map_floating_pool_row(...)` returning `FloatingPoolCreate(...)`; wire with `create_fn=lambda db_, e, u: create_floating_pool_entry(db_, e.model_dump(), u)`, `id_getter=lambda c: c.pool_id`.

- [ ] **Step 3: Uniform sanitization sweep.** Re-read all 11 `_map_<entity>_row` functions; for every string field written into a `*Create`/`csv_data`, confirm it passes through `sanitize_csv_value(...)`. Wrap any written string field that currently doesn't (do NOT wrap non-string fields, enum codes, or `value`/id keys). This is the only place behavior is intentionally tightened beyond the legacy code; note each field you newly wrapped in the commit body.

- [ ] **Step 4: Verify auth outcomes unchanged + full safety net.** From `backend/`:
```
pytest tests/test_api/test_csv_upload_characterization.py -v
```
Expected: employees/floating-pool `_requires_elevated_role` (operator → 403) and `_happy_path` (admin → 200) still PASS — proving access is preserved through the dependency swap. Then the full file + processor + comprehensive + xlsx tests all PASS.

- [ ] **Step 5: Commit.**
```bash
git add backend/endpoints/csv_upload.py
git commit -m "refactor(csv): route + normalize auth for employees/floating-pool, uniform sanitization (C2 Task 6)"
```

---

## Task 7: Final verification + PR

**Files:** none (verification).

- [ ] **Step 1: Full backend suite + coverage.** From `backend/`:
```
pytest tests/
```
Expected: all green; coverage ≥75% (and higher than pre-C2 — 9 endpoints newly covered). No permissive `assert ... in [...]` introduced.

- [ ] **Step 2: Confirm the consolidation.** `wc -l backend/endpoints/csv_upload.py` (should be far below 1181 — ~route stubs + mappers) and `grep -c "def upload_" backend/endpoints/csv_upload.py` still returns 11 (all routes intact). Confirm no `process_csv_upload`-class duplication remains (`grep -c "errors.append" backend/endpoints/csv_upload.py` → 0; it lives only in the service).

- [ ] **Step 3: Smoke.** Start the app (or rely on `e2e-sqlite`); `GET /health/live` → 200.

- [ ] **Step 4: Push + PR.**
```bash
git push -u origin refactor/csv-upload-consolidation
gh pr create --base main --head refactor/csv-upload-consolidation \
  --title "refactor(csv): consolidate 11 CSV-upload endpoints onto a shared processor (C2)" \
  --body "C2. Extracts process_csv_upload()/read_upload() into backend/services/csv_upload_processor.py; the 11 upload endpoints become thin route + _map_<entity>_row wrappers (behavior-preserving). Adds characterization tests for the 9 previously-untested endpoints (run green pre/post refactor) + processor unit tests. Robustness: employees/floating-pool inline role checks → declarative get_current_admin/get_current_planner (access identical, 403 message normalized); uniform CSV-injection sanitization. Spec/plan under docs/superpowers/."
```
Expected: 4 required checks green; report for merge approval (do not auto-merge). After merge: sync local main 0/0, confirm post-merge main CI, verify local == GitHub == Render.

---

## Self-review notes (author)

- **Spec coverage:** processor + read_upload (Task 1) · characterization of 9 untested endpoints (Tasks 2–3) · thin-endpoint extraction for all 11 (Tasks 4–6) · auth normalization employees/floating-pool (Task 6) · uniform sanitization (Task 6 Step 3) · behavior-preservation proven by green characterization pre/post (Tasks 4–6 safety-net steps) · verify + coverage-rises + PR (Task 7). All spec sections map to a task.
- **No placeholders:** Task 1 carries the full processor + unit tests; Task 2 the full worked characterization; Tasks 3–6 give complete per-endpoint mechanics bounded by the reference table + line ranges (the mappers are existing code moved verbatim — the source is cited by line, not re-invented).
- **Type/name consistency:** `process_csv_upload(rows, db, current_user, *, row_mapper, create_fn, id_getter)`, `read_upload(content, filename, sheet_name)`, `_map_<entity>_row(row, current_user)`, the `.model_dump()` `create_fn` adapter for employees/floating-pool, and the reference-table create/id symbols are used consistently across tasks.
- **Risk:** characterization happy-paths depend on each mapper accepting a minimal-valid row; Steps explicitly say to inspect the cited mapping lines and extend the CSV if a required column was missed — the golden master must pass on current code before any extraction.
```
