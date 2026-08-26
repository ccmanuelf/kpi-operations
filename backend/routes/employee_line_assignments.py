"""
Employee Line Assignments API Routes
Manage employee-to-production-line assignments with allocation tracking.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from backend.database import get_db
from backend.auth.jwt import (
    ClientScope,
    get_current_user,
    get_current_active_supervisor,
    resolve_client_scope,
)
from backend.middleware.client_auth import verify_client_access, verify_employee_access
from backend.orm.employee import Employee
from backend.orm.employee_line_assignment import EmployeeLineAssignment
from backend.orm.user import User
from backend.utils.logging_utils import get_module_logger
from backend.schemas.employee_line_assignment import (
    EmployeeLineAssignmentCreate,
    EmployeeLineAssignmentUpdate,
    EmployeeLineAssignmentResponse,
)
from backend.services.employee_line_assignment_service import (
    create_line_assignment as create_assignment,
    get_line_assignment as get_assignment,
    list_line_assignments as list_assignments,
    get_lines_for_employee as get_employee_lines,
    get_employees_for_line as get_line_employees,
    update_line_assignment as update_assignment,
    end_line_assignment as end_assignment,
)

logger = get_module_logger(__name__)

router = APIRouter(
    prefix="/api/employee-line-assignments",
    tags=["Employee Line Assignments"],
)


def _authorize_assignment(db: Session, assignment_id: int, current_user: User) -> None:
    """Authorize one line assignment for the caller before mutating it.

    SECURITY: ``update_assignment``/``end_assignment`` filter on assignment_id
    alone. 404 when absent, 403 when owned by a client the caller is not
    assigned to.
    """
    assignment = get_assignment(db, assignment_id)
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found",
        )
    verify_client_access(current_user, assignment.client_id, db)


def _authorize_employee(db: Session, employee_id: int, current_user: User) -> None:
    """Authorize reads keyed by employee id.

    SECURITY: the assignments of an employee carry that employee's client, so
    listing them for an employee outside the caller's scope leaks the other
    tenant's line topology.
    """
    employee = db.query(Employee).filter(Employee.employee_id == employee_id).first()
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found",
        )
    verify_employee_access(current_user, employee, db)


@router.get("/", response_model=List[EmployeeLineAssignmentResponse])
def list_assignments_endpoint(
    employee_id: Optional[int] = Query(None, description="Filter by employee ID"),
    line_id: Optional[int] = Query(None, description="Filter by production line ID"),
    client_id: Optional[str] = Query(None, description="Filter by client ID"),
    active_only: bool = Query(True, description="Only return active assignments"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: ClientScope = Depends(resolve_client_scope),
) -> List[EmployeeLineAssignment]:
    """
    List employee line assignments for the caller's authorized client scope.

    Filters can be combined: employee_id, line_id, client_id.
    By default returns only active assignments (end_date IS NULL or > today).

    SECURITY: ``scope`` confines the result to the caller's clients (and 403s
    an unauthorized explicit client_id). Without it this route returned every
    tenant's assignments, with or without a client_id filter.
    """
    logger.info(
        "Listing line assignments (employee_id=%s, line_id=%s, client_id=%s, active_only=%s) by user=%s",
        employee_id,
        line_id,
        client_id,
        active_only,
        current_user.user_id,
    )
    return list_assignments(
        db,
        employee_id=employee_id,
        line_id=line_id,
        client_id=client_id,
        active_only=active_only,
        client_ids=scope.client_ids,
    )


@router.get(
    "/employee/{employee_id}",
    response_model=List[EmployeeLineAssignmentResponse],
)
def get_employee_lines_endpoint(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[EmployeeLineAssignment]:
    """
    Get active line assignments for a specific employee.

    Returns the employee's current line assignments ordered by primary first.
    """
    _authorize_employee(db, employee_id, current_user)
    logger.info(
        "Getting lines for employee_id=%d by user=%s",
        employee_id,
        current_user.user_id,
    )
    return get_employee_lines(db, employee_id)


@router.get(
    "/line/{line_id}",
    response_model=List[EmployeeLineAssignmentResponse],
)
def get_line_employees_endpoint(
    line_id: int,
    client_id: str = Query(..., description="Client ID for tenant isolation"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[EmployeeLineAssignment]:
    """
    Get active employees assigned to a specific production line.

    Requires client_id for multi-tenant isolation.
    Returns assignments ordered by primary first.
    """
    # SECURITY: client_id arrives from the caller; confirm they own it.
    verify_client_access(current_user, client_id, db)
    logger.info(
        "Getting employees for line_id=%d, client_id=%s by user=%s",
        line_id,
        client_id,
        current_user.user_id,
    )
    return get_line_employees(db, line_id, client_id)


@router.post(
    "/",
    response_model=EmployeeLineAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_assignment_endpoint(
    data: EmployeeLineAssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor),
) -> EmployeeLineAssignment:
    """
    Create a new employee-to-line assignment.

    Requires supervisor or admin role.

    Business rules enforced:
    - Max 2 active assignments per employee
    - Total allocation cannot exceed 100%
    - First assignment is always marked as primary
    """
    try:
        result = create_assignment(db, data)
    except ValueError as exc:
        error_msg = str(exc)
        if "Duplicate" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=error_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=error_msg,
        )
    logger.info(
        "Created line assignment: employee_id=%d -> line_id=%d by user=%s",
        data.employee_id,
        data.line_id,
        current_user.user_id,
    )
    return result


@router.put(
    "/{assignment_id}",
    response_model=EmployeeLineAssignmentResponse,
)
def update_assignment_endpoint(
    assignment_id: int,
    data: EmployeeLineAssignmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor),
) -> EmployeeLineAssignment:
    """
    Update an existing employee line assignment.

    Requires supervisor or admin role.
    Re-validates allocation if percentage changes.
    """
    _authorize_assignment(db, assignment_id, current_user)
    try:
        result = update_assignment(db, assignment_id, data)
    except ValueError as exc:
        logger.info("Assignment update rejected for assignment_id=%d: %s", assignment_id, exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Total allocation across line assignments cannot exceed 100%",
        )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found",
        )
    logger.info(
        "Updated line assignment assignment_id=%d by user=%s",
        assignment_id,
        current_user.user_id,
    )
    return result


@router.delete(
    "/{assignment_id}",
    response_model=EmployeeLineAssignmentResponse,
)
def end_assignment_endpoint(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor),
) -> EmployeeLineAssignment:
    """
    End an employee line assignment (sets end_date to today).

    Requires supervisor or admin role.
    Does NOT hard-delete; sets end_date for audit trail.
    """
    _authorize_assignment(db, assignment_id, current_user)
    result = end_assignment(db, assignment_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found",
        )
    logger.info(
        "Ended line assignment assignment_id=%d by user=%s",
        assignment_id,
        current_user.user_id,
    )
    return result
