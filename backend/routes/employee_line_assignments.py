"""
Employee Line Assignments API Routes
Manage employee-to-production-line assignments with allocation tracking.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from backend.database import get_db
from backend.auth.jwt import get_current_user, get_current_active_supervisor
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


@router.get("/", response_model=List[EmployeeLineAssignmentResponse])
def list_assignments_endpoint(
    employee_id: Optional[int] = Query(None, description="Filter by employee ID"),
    line_id: Optional[int] = Query(None, description="Filter by production line ID"),
    client_id: Optional[str] = Query(None, description="Filter by client ID"),
    active_only: bool = Query(True, description="Only return active assignments"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[EmployeeLineAssignment]:
    """
    List employee line assignments with optional filters.

    Filters can be combined: employee_id, line_id, client_id.
    By default returns only active assignments (end_date IS NULL or > today).
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
    try:
        result = update_assignment(db, assignment_id, data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
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
