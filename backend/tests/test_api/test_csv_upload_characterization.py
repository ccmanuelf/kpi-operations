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


# ==================== HOLDS ====================


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
    monkeypatch.setattr(
        "backend.endpoints.csv_upload.create_wip_hold",
        lambda db, e, u: _Created(hold_entry_id="X"),
    )
    # Missing required client_id → mapper raises → counted as failed (create never called)
    content = _csv_bytes("client_id,work_order_number", ",WO-1")
    resp = test_client.post("/api/holds/upload/csv", files=_files(content), headers=admin_auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["failed"] == 1
    assert body["successful"] == 0
    assert body["errors"][0]["row"] == 2
    assert body["errors"][0]["error"] == "Data parsing error in CSV row"


def test_holds_requires_elevated_role(test_client, auth_headers):
    # auth_headers self-registers => operator => 403 on this supervisor-tier endpoint
    content = _csv_bytes("client_id,work_order_number", "CLIENT-A,WO-1")
    resp = test_client.post("/api/holds/upload/csv", files=_files(content), headers=auth_headers)
    assert resp.status_code == 403


# ==================== ATTENDANCE ====================


def test_attendance_happy_path(test_client, admin_auth_headers, monkeypatch):
    captured = {}

    def stub(db, entry, user):
        captured["entry"] = entry
        return _Created(attendance_entry_id="A-1")

    monkeypatch.setattr("backend.endpoints.csv_upload.create_attendance_record", stub)
    # Required: client_id, employee_id, shift_date, scheduled_hours
    content = _csv_bytes(
        "client_id,employee_id,shift_date,scheduled_hours",
        "CLIENT-A,1,2024-01-15,8",
    )
    resp = test_client.post("/api/attendance/upload/csv", files=_files(content), headers=admin_auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["successful"] == 1
    assert body["failed"] == 0
    assert body["created_entries"] == ["A-1"]
    assert captured["entry"] is not None


def test_attendance_invalid_row_recorded(test_client, admin_auth_headers, monkeypatch):
    monkeypatch.setattr(
        "backend.endpoints.csv_upload.create_attendance_record",
        lambda db, e, u: _Created(attendance_entry_id="X"),
    )
    # Missing required client_id → ValueError("client_id is required") → Data parsing error
    content = _csv_bytes(
        "client_id,employee_id,shift_date,scheduled_hours",
        ",1,2024-01-15,8",
    )
    resp = test_client.post("/api/attendance/upload/csv", files=_files(content), headers=admin_auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["failed"] == 1
    assert body["successful"] == 0
    assert body["errors"][0]["row"] == 2
    assert body["errors"][0]["error"] == "Data parsing error in CSV row"


def test_attendance_requires_elevated_role(test_client, auth_headers):
    content = _csv_bytes(
        "client_id,employee_id,shift_date,scheduled_hours",
        "CLIENT-A,1,2024-01-15,8",
    )
    resp = test_client.post("/api/attendance/upload/csv", files=_files(content), headers=auth_headers)
    assert resp.status_code == 403


# ==================== COVERAGE ====================


def test_coverage_happy_path(test_client, admin_auth_headers, monkeypatch):
    captured = {}

    def stub(db, entry, user):
        captured["entry"] = entry
        return _Created(coverage_id="COV-1")

    monkeypatch.setattr("backend.endpoints.csv_upload.create_shift_coverage", stub)
    # Required: client_id, shift_id, coverage_date, required_employees, actual_employees
    content = _csv_bytes(
        "client_id,shift_id,coverage_date,required_employees,actual_employees",
        "CLIENT-A,1,2024-01-15,5,4",
    )
    resp = test_client.post("/api/coverage/upload/csv", files=_files(content), headers=admin_auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["successful"] == 1
    assert body["failed"] == 0
    assert body["created_entries"] == ["COV-1"]
    assert captured["entry"] is not None


def test_coverage_invalid_row_recorded(test_client, admin_auth_headers, monkeypatch):
    monkeypatch.setattr(
        "backend.endpoints.csv_upload.create_shift_coverage",
        lambda db, e, u: _Created(coverage_id="X"),
    )
    # Missing required client_id → ValueError("client_id is required") → Data parsing error
    content = _csv_bytes(
        "client_id,shift_id,coverage_date,required_employees,actual_employees",
        ",1,2024-01-15,5,4",
    )
    resp = test_client.post("/api/coverage/upload/csv", files=_files(content), headers=admin_auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["failed"] == 1
    assert body["successful"] == 0
    assert body["errors"][0]["row"] == 2
    assert body["errors"][0]["error"] == "Data parsing error in CSV row"


def test_coverage_requires_elevated_role(test_client, auth_headers):
    content = _csv_bytes(
        "client_id,shift_id,coverage_date,required_employees,actual_employees",
        "CLIENT-A,1,2024-01-15,5,4",
    )
    resp = test_client.post("/api/coverage/upload/csv", files=_files(content), headers=auth_headers)
    assert resp.status_code == 403


# ==================== QUALITY ====================


def test_quality_happy_path(test_client, admin_auth_headers, monkeypatch):
    captured = {}

    def stub(db, entry, user):
        captured["entry"] = entry
        return _Created(quality_entry_id="Q-1")

    monkeypatch.setattr("backend.endpoints.csv_upload.create_quality_inspection", stub)
    # Required: client_id, work_order_number, shift_date, units_inspected, units_passed
    content = _csv_bytes(
        "client_id,work_order_number,shift_date,units_inspected,units_passed",
        "CLIENT-A,WO-1,2024-01-15,100,95",
    )
    resp = test_client.post("/api/quality/upload/csv", files=_files(content), headers=admin_auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["successful"] == 1
    assert body["failed"] == 0
    assert body["created_entries"] == ["Q-1"]
    assert captured["entry"] is not None


def test_quality_invalid_row_recorded(test_client, admin_auth_headers, monkeypatch):
    monkeypatch.setattr(
        "backend.endpoints.csv_upload.create_quality_inspection",
        lambda db, e, u: _Created(quality_entry_id="X"),
    )
    # Missing required client_id → ValueError → Data parsing error
    content = _csv_bytes(
        "client_id,work_order_number,shift_date,units_inspected,units_passed",
        ",WO-1,2024-01-15,100,95",
    )
    resp = test_client.post("/api/quality/upload/csv", files=_files(content), headers=admin_auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["failed"] == 1
    assert body["successful"] == 0
    assert body["errors"][0]["row"] == 2
    assert body["errors"][0]["error"] == "Data parsing error in CSV row"


def test_quality_requires_elevated_role(test_client, auth_headers):
    content = _csv_bytes(
        "client_id,work_order_number,shift_date,units_inspected,units_passed",
        "CLIENT-A,WO-1,2024-01-15,100,95",
    )
    resp = test_client.post("/api/quality/upload/csv", files=_files(content), headers=auth_headers)
    assert resp.status_code == 403


# ==================== DEFECTS ====================


def test_defects_happy_path(test_client, admin_auth_headers, monkeypatch):
    captured = {}

    def stub(db, data, user):
        captured["data"] = data
        return _Created(defect_detail_id="DD-1")

    monkeypatch.setattr("backend.endpoints.csv_upload.create_defect_detail", stub)
    # Required: defect_detail_id, quality_entry_id, client_id_fk, defect_type, defect_count
    content = _csv_bytes(
        "defect_detail_id,quality_entry_id,client_id_fk,defect_type,defect_count",
        "DD-001,QE-001,CLIENT-A,Stitching,3",
    )
    resp = test_client.post("/api/defects/upload/csv", files=_files(content), headers=admin_auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["successful"] == 1
    assert body["failed"] == 0
    assert body["created_entries"] == ["DD-1"]
    assert captured["data"] is not None


def test_defects_invalid_row_recorded(test_client, admin_auth_headers, monkeypatch):
    monkeypatch.setattr(
        "backend.endpoints.csv_upload.create_defect_detail",
        lambda db, d, u: _Created(defect_detail_id="X"),
    )
    # Missing required defect_count → int("") raises ValueError → Data parsing error
    content = _csv_bytes(
        "defect_detail_id,quality_entry_id,client_id_fk,defect_type,defect_count",
        "DD-001,QE-001,CLIENT-A,Stitching,",
    )
    resp = test_client.post("/api/defects/upload/csv", files=_files(content), headers=admin_auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["failed"] == 1
    assert body["successful"] == 0
    assert body["errors"][0]["row"] == 2
    assert body["errors"][0]["error"] == "Data parsing error in CSV row"


def test_defects_requires_elevated_role(test_client, auth_headers):
    content = _csv_bytes(
        "defect_detail_id,quality_entry_id,client_id_fk,defect_type,defect_count",
        "DD-001,QE-001,CLIENT-A,Stitching,3",
    )
    resp = test_client.post("/api/defects/upload/csv", files=_files(content), headers=auth_headers)
    assert resp.status_code == 403


# ==================== JOBS ====================


def test_jobs_happy_path(test_client, admin_auth_headers, monkeypatch):
    captured = {}

    def stub(db, data, user):
        captured["data"] = data
        return _Created(job_id="JOB-1")

    monkeypatch.setattr("backend.endpoints.csv_upload.create_job", stub)
    # Required: job_id, work_order_id, client_id_fk, operation_name, sequence_number
    content = _csv_bytes(
        "job_id,work_order_id,client_id_fk,operation_name,sequence_number",
        "JOB-001,WO-001,CLIENT-A,Cutting,1",
    )
    resp = test_client.post("/api/jobs/upload/csv", files=_files(content), headers=admin_auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["successful"] == 1
    assert body["failed"] == 0
    assert body["created_entries"] == ["JOB-1"]
    assert captured["data"] is not None


def test_jobs_invalid_row_recorded(test_client, admin_auth_headers, monkeypatch):
    monkeypatch.setattr(
        "backend.endpoints.csv_upload.create_job",
        lambda db, d, u: _Created(job_id="X"),
    )
    # Missing required sequence_number → int("") raises ValueError → Data parsing error
    content = _csv_bytes(
        "job_id,work_order_id,client_id_fk,operation_name,sequence_number",
        "JOB-001,WO-001,CLIENT-A,Cutting,",
    )
    resp = test_client.post("/api/jobs/upload/csv", files=_files(content), headers=admin_auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["failed"] == 1
    assert body["successful"] == 0
    assert body["errors"][0]["row"] == 2
    assert body["errors"][0]["error"] == "Data parsing error in CSV row"


def test_jobs_requires_elevated_role(test_client, auth_headers):
    content = _csv_bytes(
        "job_id,work_order_id,client_id_fk,operation_name,sequence_number",
        "JOB-001,WO-001,CLIENT-A,Cutting,1",
    )
    resp = test_client.post("/api/jobs/upload/csv", files=_files(content), headers=auth_headers)
    assert resp.status_code == 403


# ==================== CLIENTS ====================


def test_clients_happy_path(test_client, admin_auth_headers, monkeypatch):
    captured = {}

    def stub(db, data, user):
        captured["data"] = data
        return _Created(client_id="CLI-1")

    monkeypatch.setattr("backend.endpoints.csv_upload.create_client", stub)
    # Required: client_id, client_name
    content = _csv_bytes(
        "client_id,client_name",
        "CLI-001,Acme Corp",
    )
    resp = test_client.post("/api/clients/upload/csv", files=_files(content), headers=admin_auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["successful"] == 1
    assert body["failed"] == 0
    assert body["created_entries"] == ["CLI-1"]
    assert captured["data"] is not None


def test_clients_invalid_row_recorded(test_client, admin_auth_headers, monkeypatch):
    monkeypatch.setattr(
        "backend.endpoints.csv_upload.create_client",
        lambda db, d, u: _Created(client_id="X"),
    )
    # Missing required client_name → KeyError → Data parsing error
    content = _csv_bytes(
        "client_id",
        "CLI-001",
    )
    resp = test_client.post("/api/clients/upload/csv", files=_files(content), headers=admin_auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["failed"] == 1
    assert body["successful"] == 0
    assert body["errors"][0]["row"] == 2
    assert body["errors"][0]["error"] == "Data parsing error in CSV row"


def test_clients_requires_elevated_role(test_client, auth_headers):
    # auth_headers = operator; clients endpoint uses get_current_admin → 403
    content = _csv_bytes(
        "client_id,client_name",
        "CLI-001,Acme Corp",
    )
    resp = test_client.post("/api/clients/upload/csv", files=_files(content), headers=auth_headers)
    assert resp.status_code == 403


# ==================== EMPLOYEES ====================


def test_employees_happy_path(test_client, admin_auth_headers, monkeypatch):
    captured = {}

    def stub(db, data, user):
        captured["data"] = data
        return _Created(employee_id="EMP-1")

    monkeypatch.setattr("backend.endpoints.csv_upload.create_employee", stub)
    # Required: employee_code, employee_name
    content = _csv_bytes(
        "employee_code,employee_name",
        "EMP-001,Jane Doe",
    )
    resp = test_client.post("/api/employees/upload/csv", files=_files(content), headers=admin_auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["successful"] == 1
    assert body["failed"] == 0
    assert body["created_entries"] == ["EMP-1"]
    assert captured["data"] is not None


def test_employees_invalid_row_recorded(test_client, admin_auth_headers, monkeypatch):
    monkeypatch.setattr(
        "backend.endpoints.csv_upload.create_employee",
        lambda db, d, u: _Created(employee_id="X"),
    )
    # Missing required employee_name → KeyError → Data parsing error
    content = _csv_bytes(
        "employee_code",
        "EMP-001",
    )
    resp = test_client.post("/api/employees/upload/csv", files=_files(content), headers=admin_auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["failed"] == 1
    assert body["successful"] == 0
    assert body["errors"][0]["row"] == 2
    assert body["errors"][0]["error"] == "Data parsing error in CSV row"


def test_employees_requires_elevated_role(test_client, auth_headers):
    # auth_headers = operator; 403 from get_current_admin dependency
    content = _csv_bytes(
        "employee_code,employee_name",
        "EMP-001,Jane Doe",
    )
    resp = test_client.post("/api/employees/upload/csv", files=_files(content), headers=auth_headers)
    assert resp.status_code == 403


# ==================== FLOATING POOL ====================


def test_floating_pool_happy_path(test_client, admin_auth_headers, monkeypatch):
    captured = {}

    def stub(db, data, user):
        captured["data"] = data
        return _Created(pool_id="POOL-1")

    monkeypatch.setattr("backend.endpoints.csv_upload.create_floating_pool_entry", stub)
    # Required: employee_id
    content = _csv_bytes(
        "employee_id",
        "42",
    )
    resp = test_client.post("/api/floating-pool/upload/csv", files=_files(content), headers=admin_auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["successful"] == 1
    assert body["failed"] == 0
    assert body["created_entries"] == ["POOL-1"]
    assert captured["data"] is not None


def test_floating_pool_invalid_row_recorded(test_client, admin_auth_headers, monkeypatch):
    monkeypatch.setattr(
        "backend.endpoints.csv_upload.create_floating_pool_entry",
        lambda db, d, u: _Created(pool_id="X"),
    )
    # Non-numeric employee_id → int("not-a-number") raises ValueError → Data parsing error
    content = _csv_bytes(
        "employee_id",
        "not-a-number",
    )
    resp = test_client.post("/api/floating-pool/upload/csv", files=_files(content), headers=admin_auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["failed"] == 1
    assert body["successful"] == 0
    assert body["errors"][0]["row"] == 2
    assert body["errors"][0]["error"] == "Data parsing error in CSV row"


def test_floating_pool_requires_elevated_role(test_client, auth_headers):
    # auth_headers = operator; floating-pool endpoint requires ADMIN or POWERUSER → 403
    content = _csv_bytes(
        "employee_id",
        "42",
    )
    resp = test_client.post("/api/floating-pool/upload/csv", files=_files(content), headers=auth_headers)
    assert resp.status_code == 403


# ==================== DOWNTIME ====================


def test_downtime_happy_path(test_client, admin_auth_headers, monkeypatch):
    captured = {}

    def stub(db, entry, user):
        captured["entry"] = entry
        return _Created(downtime_entry_id="DT-1")

    monkeypatch.setattr("backend.endpoints.csv_upload.create_downtime_event", stub)
    # Required: client_id, shift_date (YYYY-MM-DD), duration_hours (→ minutes via from_legacy_csv)
    content = _csv_bytes(
        "client_id,shift_date,duration_hours",
        "CLIENT-A,2024-01-15,1",
    )
    resp = test_client.post("/api/downtime/upload/csv", files=_files(content), headers=admin_auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["successful"] == 1
    assert body["failed"] == 0
    assert body["created_entries"] == ["DT-1"]
    assert captured["entry"] is not None  # mapper produced a schema object


def test_downtime_invalid_row_recorded(test_client, admin_auth_headers, monkeypatch):
    monkeypatch.setattr(
        "backend.endpoints.csv_upload.create_downtime_event",
        lambda db, e, u: _Created(downtime_entry_id="X"),
    )
    # Missing required client_id → ValueError("client_id is required") → Data parsing error
    content = _csv_bytes(
        "client_id,shift_date,duration_hours",
        ",2024-01-15,1",
    )
    resp = test_client.post("/api/downtime/upload/csv", files=_files(content), headers=admin_auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["failed"] == 1
    assert body["successful"] == 0
    assert body["errors"][0]["row"] == 2
    assert body["errors"][0]["error"] == "Data parsing error in CSV row"


def test_downtime_requires_elevated_role(test_client, auth_headers):
    # auth_headers = operator; downtime endpoint requires supervisor → 403
    content = _csv_bytes(
        "client_id,shift_date,duration_hours",
        "CLIENT-A,2024-01-15,1",
    )
    resp = test_client.post("/api/downtime/upload/csv", files=_files(content), headers=auth_headers)
    assert resp.status_code == 403


# ==================== WORK ORDERS ====================


def test_work_orders_happy_path(test_client, admin_auth_headers, monkeypatch):
    captured = {}

    def stub(db, data, user):
        captured["data"] = data
        return _Created(work_order_id="WO-1")

    monkeypatch.setattr("backend.endpoints.csv_upload.create_work_order", stub)
    # Required: work_order_id, client_id, style_model, planned_quantity
    # priority must match pattern ^(URGENT|HIGH|NORMAL|MEDIUM|LOW)$ (empty string fails validation)
    content = _csv_bytes(
        "work_order_id,client_id,style_model,planned_quantity,priority",
        "WO-001,CLIENT-A,Style-X,100,HIGH",
    )
    resp = test_client.post("/api/work-orders/upload/csv", files=_files(content), headers=admin_auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["successful"] == 1
    assert body["failed"] == 0
    assert body["created_entries"] == ["WO-1"]
    assert captured["data"] is not None  # mapper produced a schema object


def test_work_orders_invalid_row_recorded(test_client, admin_auth_headers, monkeypatch):
    monkeypatch.setattr(
        "backend.endpoints.csv_upload.create_work_order",
        lambda db, d, u: _Created(work_order_id="X"),
    )
    # Missing required client_id column → row["client_id"] KeyError → Data parsing error
    content = _csv_bytes(
        "work_order_id,style_model,planned_quantity",
        "WO-001,Style-X,100",
    )
    resp = test_client.post("/api/work-orders/upload/csv", files=_files(content), headers=admin_auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["failed"] == 1
    assert body["successful"] == 0
    assert body["errors"][0]["row"] == 2
    assert body["errors"][0]["error"] == "Data parsing error in CSV row"


def test_work_orders_requires_elevated_role(test_client, auth_headers):
    # auth_headers = operator; work-orders endpoint requires supervisor → 403
    content = _csv_bytes(
        "work_order_id,client_id,style_model,planned_quantity,priority",
        "WO-001,CLIENT-A,Style-X,100,HIGH",
    )
    resp = test_client.post("/api/work-orders/upload/csv", files=_files(content), headers=auth_headers)
    assert resp.status_code == 403
