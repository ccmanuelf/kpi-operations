"""
Employee Service
Service layer for Employee operations.
Coordinates CRUD operations with floating pool logic and client assignment.

Phase 2: Service Layer Enforcement
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import Depends

from backend.schemas.employee import Employee
from backend.schemas.user import User
from backend.crud.employee import (
    create_employee,
    get_employee,
    get_employees,
    update_employee,
    delete_employee,
    get_floating_pool_employees,
    assign_to_floating_pool,
    remove_from_floating_pool,
    get_employees_by_client,
    assign_employee_to_client,
)
from backend.database import get_db


class EmployeeService:
    """
    Service layer for Employee operations.

    Wraps employee CRUD with business logic:
    - Floating pool membership management
    - Client assignment tracking
    - Role-based access control
    """

    def __init__(self, db: Session):
        """
        Initialize service with database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def create_employee(
        self,
        data: dict,
        user: User
    ) -> Employee:
        """
        Create a new employee.

        Args:
            data: Employee data dictionary
            user: Authenticated user

        Returns:
            Created employee
        """
        return create_employee(self.db, data, user)

    def get_employee(
        self,
        employee_id: int,
        user: User
    ) -> Optional[Employee]:
        """
        Get an employee by ID.

        Args:
            employee_id: Employee ID
            user: Authenticated user

        Returns:
            Employee or None
        """
        return get_employee(self.db, employee_id, user)

    def list_employees(
        self,
        user: User,
        skip: int = 0,
        limit: int = 100,
        client_id: Optional[str] = None,
        is_floating_pool: Optional[bool] = None
    ) -> List[Employee]:
        """
        List employees with filtering.

        Args:
            user: Authenticated user
            skip: Records to skip
            limit: Maximum records
            client_id: Filter by client assignment
            is_floating_pool: Filter by floating pool status

        Returns:
            List of employees
        """
        return get_employees(
            self.db, user, skip, limit, client_id, is_floating_pool
        )

    def update_employee(
        self,
        employee_id: int,
        data: dict,
        user: User
    ) -> Optional[Employee]:
        """
        Update an employee.

        Args:
            employee_id: Employee ID
            data: Update data
            user: Authenticated user

        Returns:
            Updated employee
        """
        return update_employee(self.db, employee_id, data, user)

    def delete_employee(
        self,
        employee_id: int,
        user: User
    ) -> bool:
        """
        Soft delete an employee.

        Args:
            employee_id: Employee ID
            user: Authenticated user

        Returns:
            True if deleted
        """
        return delete_employee(self.db, employee_id, user)

    # Floating Pool Operations

    def get_floating_pool_employees(
        self,
        user: User,
        skip: int = 0,
        limit: int = 100
    ) -> List[Employee]:
        """
        Get all floating pool employees.

        Args:
            user: Authenticated user
            skip: Records to skip
            limit: Maximum records

        Returns:
            List of floating pool employees
        """
        return get_floating_pool_employees(self.db, user, skip, limit)

    def assign_to_floating_pool(
        self,
        employee_id: int,
        user: User
    ) -> Employee:
        """
        Assign an employee to the floating pool.

        Args:
            employee_id: Employee ID
            user: Authenticated user

        Returns:
            Updated employee
        """
        return assign_to_floating_pool(self.db, employee_id, user)

    def remove_from_floating_pool(
        self,
        employee_id: int,
        user: User
    ) -> Employee:
        """
        Remove an employee from the floating pool.

        Args:
            employee_id: Employee ID
            user: Authenticated user

        Returns:
            Updated employee
        """
        return remove_from_floating_pool(self.db, employee_id, user)

    # Client Assignment Operations

    def get_employees_by_client(
        self,
        client_id: str,
        user: User,
        skip: int = 0,
        limit: int = 100
    ) -> List[Employee]:
        """
        Get all employees assigned to a client.

        Args:
            client_id: Client ID
            user: Authenticated user
            skip: Records to skip
            limit: Maximum records

        Returns:
            List of employees
        """
        return get_employees_by_client(self.db, client_id, user, skip, limit)

    def assign_employee_to_client(
        self,
        employee_id: int,
        client_id: str,
        user: User
    ) -> Employee:
        """
        Assign an employee to a client.

        Args:
            employee_id: Employee ID
            client_id: Client ID
            user: Authenticated user

        Returns:
            Updated employee
        """
        return assign_employee_to_client(self.db, employee_id, client_id, user)


def get_employee_service(db: Session = Depends(get_db)) -> EmployeeService:
    """
    FastAPI dependency to get EmployeeService instance.
    """
    return EmployeeService(db)
