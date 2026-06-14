"""
CRUD-layer authorization alignment (Run 7 follow-up).

Run 7 widened the route guards to the supervisory tier (admin, poweruser,
leader, supervisor) but six CRUD modules still enforced a stale
["admin", "supervisor"] list, so a PowerUser or Leader passed the route guard
and was then 403'd inside the CRUD function — contradicting the documented
permission matrix. These tests pin the fix at the CRUD layer (where the route
permission-matrix tests, which send empty bodies, never reach):

- every supervisory-tier role can create employees / floating-pool entries /
  manage global defect types
- operator and viewer are denied

The route permission-matrix test cannot catch this because an empty body
fails Pydantic validation (422) before the handler calls into CRUD.
"""

import pathlib
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.crud.employee.core import create_employee
from backend.crud.floating_pool.core import create_floating_pool_entry
from backend.orm.user import SUPERVISORY_ROLES

# The six CRUD modules Run 7 realigned from the stale ["admin", "supervisor"]
# list to the canonical supervisory tier.
_RECONCILED_CRUD_FILES = [
    "backend/crud/employee/core.py",
    "backend/crud/employee/client_assignment.py",
    "backend/crud/employee/floating_pool.py",
    "backend/crud/floating_pool/core.py",
    "backend/crud/floating_pool/assignments.py",
    "backend/crud/defect_type_catalog.py",
]
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]


def _user(role):
    return SimpleNamespace(user_id=f"USR-{role}", username=role, role=role, client_id_assigned="ACME-MFG")


SUPERVISORY = ["admin", "poweruser", "leader", "supervisor"]
DENIED = ["operator", "viewer"]


class TestCrudRoleAlignment:
    def test_supervisory_tier_constant_is_correct(self):
        assert set(SUPERVISORY_ROLES) == set(SUPERVISORY)
        assert "operator" not in SUPERVISORY_ROLES
        assert "viewer" not in SUPERVISORY_ROLES

    @pytest.mark.parametrize("role", SUPERVISORY)
    def test_supervisory_roles_pass_employee_crud_guard(self, transactional_db, role):
        """admin/poweruser/leader/supervisor must clear the create_employee
        role gate (poweruser & leader were the regression)."""
        emp = create_employee(
            transactional_db,
            {
                "client_id_assigned": "ACME-MFG",
                "employee_code": f"EMP-{role}-001",
                "employee_name": f"{role} Created",
            },
            _user(role),
        )
        assert emp.employee_code == f"EMP-{role}-001"

    @pytest.mark.parametrize("role", DENIED)
    def test_denied_roles_blocked_from_employee_crud(self, transactional_db, role):
        with pytest.raises(HTTPException) as exc:
            create_employee(
                transactional_db,
                {"client_id_assigned": "ACME-MFG", "employee_code": "EMP-X", "employee_name": "x"},
                _user(role),
            )
        assert exc.value.status_code == 403

    @pytest.mark.parametrize("role", ["poweruser", "leader"])
    def test_poweruser_leader_pass_floating_pool_guard(self, transactional_db, role):
        """The two roles the stale list silently denied must now pass.

        A non-existent employee_id makes the call raise 404 — which proves we
        got past the 403 role gate (the regression).
        """
        with pytest.raises(HTTPException) as exc:
            create_floating_pool_entry(
                transactional_db,
                {"employee_id": 999999},
                _user(role),
            )
        assert exc.value.status_code == 404, f"{role} expected 404 (past guard), got {exc.value.status_code}"

    @pytest.mark.parametrize("rel", _RECONCILED_CRUD_FILES)
    def test_reconciled_files_use_canonical_tier(self, rel):
        """No reconciled CRUD module may carry the stale ['admin','supervisor']
        list; each must reference the shared SUPERVISORY_ROLES constant."""
        src = (_REPO_ROOT / rel).read_text()
        assert '["admin", "supervisor"]' not in src, f"{rel} still has the stale role list"
        assert "SUPERVISORY_ROLES" in src, f"{rel} does not reference SUPERVISORY_ROLES"
