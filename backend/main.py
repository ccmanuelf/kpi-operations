"""
Manufacturing KPI Platform - FastAPI Backend
Main application with all routes
"""
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, datetime, timedelta
import io
import csv
import json
import uuid
from decimal import Decimal
from jose import JWTError, jwt

from backend.config import settings
from backend.database import get_db, engine, Base
from backend.models.user import UserCreate, UserLogin, UserResponse, UserUpdate, Token, PasswordResetRequest, PasswordResetConfirm, PasswordChange
from backend.middleware.rate_limit import (
    limiter,
    configure_rate_limiting,
    RateLimitConfig
)
from backend.auth.password_policy import validate_password_strength
from backend.models.production import (
    ProductionEntryCreate,
    ProductionEntryUpdate,
    ProductionEntryResponse,
    ProductionEntryWithKPIs,
    CSVUploadResponse,
    KPICalculationResponse
)
from backend.models.import_log import (
    BatchImportRequest,
    BatchImportResponse
)
from backend.models.downtime import (
    DowntimeEventCreate,
    DowntimeEventUpdate,
    DowntimeEventResponse,
    AvailabilityCalculationResponse
)
from backend.models.hold import (
    WIPHoldCreate,
    WIPHoldUpdate,
    WIPHoldResponse,
    WIPAgingResponse
)
from backend.models.attendance import (
    AttendanceRecordCreate,
    AttendanceRecordUpdate,
    AttendanceRecordResponse,
    AbsenteeismCalculationResponse
)
from backend.models.coverage import (
    ShiftCoverageCreate,
    ShiftCoverageUpdate,
    ShiftCoverageResponse
)
from backend.models.quality import (
    QualityInspectionCreate,
    QualityInspectionUpdate,
    QualityInspectionResponse,
    PPMCalculationResponse,
    DPMOCalculationResponse,
    FPYRTYCalculationResponse
)
from backend.models.job import (
    JobCreate,
    JobUpdate,
    JobComplete,
    JobResponse
)
from backend.models.part_opportunities import (
    PartOpportunityCreate,
    PartOpportunityUpdate,
    PartOpportunityResponse,
    BulkImportRequest,
    BulkImportResponse
)
from backend.models.defect_detail import (
    DefectDetailCreate,
    DefectDetailUpdate,
    DefectDetailResponse,
    DefectSummaryResponse
)
from backend.models.work_order import (
    WorkOrderCreate,
    WorkOrderUpdate,
    WorkOrderResponse,
    WorkOrderWithMetrics
)
from backend.models.client import (
    ClientCreate,
    ClientUpdate,
    ClientResponse,
    ClientSummary
)
from backend.models.employee import (
    EmployeeCreate,
    EmployeeUpdate,
    EmployeeResponse,
    EmployeeWithClients,
    EmployeeAssignmentRequest,
    FloatingPoolAssignmentRequest as EmployeeFloatingPoolRequest
)
from backend.models.floating_pool import (
    FloatingPoolCreate,
    FloatingPoolUpdate,
    FloatingPoolResponse,
    FloatingPoolAssignmentRequest,
    FloatingPoolUnassignmentRequest,
    FloatingPoolAvailability,
    FloatingPoolSummary
)
from backend.schemas.user import User
from backend.schemas.product import Product
from backend.schemas.shift import Shift
from backend.auth.jwt import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_user,
    get_current_active_supervisor,
    oauth2_scheme  # For logout endpoint token extraction
)
from backend.crud.production import (
    create_production_entry,
    get_production_entry,
    get_production_entries,
    update_production_entry,
    delete_production_entry,
    get_production_entry_with_details,
    get_daily_summary
)
from backend.crud.downtime import (
    create_downtime_event,
    get_downtime_event,
    get_downtime_events,
    update_downtime_event,
    delete_downtime_event
)
from backend.crud.hold import (
    create_wip_hold,
    get_wip_hold,
    get_wip_holds,
    update_wip_hold,
    delete_wip_hold
)
from backend.crud.attendance import (
    create_attendance_record,
    get_attendance_record,
    get_attendance_records,
    update_attendance_record,
    delete_attendance_record
)
from backend.crud.job import (
    create_job,
    get_job,
    get_jobs,
    get_jobs_by_work_order,
    update_job,
    delete_job,
    complete_job
)
from backend.crud.part_opportunities import (
    create_part_opportunity,
    get_part_opportunity,
    get_part_opportunities,
    get_part_opportunities_by_category,
    update_part_opportunity,
    delete_part_opportunity,
    bulk_import_opportunities
)
from backend.crud.coverage import (
    create_shift_coverage,
    get_shift_coverage,
    get_shift_coverages,
    update_shift_coverage,
    delete_shift_coverage
)
from backend.crud.quality import (
    create_quality_inspection,
    get_quality_inspection,
    get_quality_inspections,
    update_quality_inspection,
    delete_quality_inspection
)
from backend.crud.defect_detail import (
    create_defect_detail,
    get_defect_detail,
    get_defect_details,
    get_defect_details_by_quality_entry,
    update_defect_detail,
    delete_defect_detail,
    get_defect_summary_by_type
)
from backend.crud.work_order import (
    create_work_order,
    get_work_order,
    get_work_orders,
    update_work_order,
    delete_work_order,
    get_work_orders_by_client,
    get_work_orders_by_status,
    get_work_orders_by_date_range
)
from backend.crud.client import (
    create_client,
    get_client,
    get_clients,
    update_client,
    delete_client,
    get_active_clients
)
from backend.crud.employee import (
    create_employee,
    get_employee,
    get_employees,
    update_employee,
    delete_employee,
    get_employees_by_client,
    get_floating_pool_employees,
    assign_to_floating_pool,
    remove_from_floating_pool,
    assign_employee_to_client
)
from backend.crud.floating_pool import (
    create_floating_pool_entry,
    get_floating_pool_entry,
    get_floating_pool_entries,
    update_floating_pool_entry,
    delete_floating_pool_entry,
    assign_floating_pool_to_client,
    unassign_floating_pool_from_client,
    get_available_floating_pool_employees,
    get_floating_pool_assignments_by_client
)
from backend.calculations.efficiency import calculate_efficiency
from backend.calculations.performance import calculate_performance, calculate_quality_rate
from backend.calculations.availability import calculate_availability
from backend.calculations.wip_aging import calculate_wip_aging, identify_chronic_holds
from backend.calculations.absenteeism import calculate_absenteeism, calculate_bradford_factor
from backend.calculations.otd import calculate_otd, identify_late_orders
from backend.calculations.ppm import calculate_ppm, identify_top_defects
from backend.calculations.dpmo import calculate_dpmo
from backend.calculations.fpy_rty import calculate_fpy, calculate_rty, calculate_quality_score
from backend.calculations.inference import InferenceEngine
# PDFReportGenerator is imported later when needed for report endpoints

# Create tables (DISABLED - using pre-populated SQLite database with demo data)
# Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI(
    title="Manufacturing KPI Platform API",
    description="FastAPI backend for production tracking and KPI calculation",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting middleware (SEC-001)
configure_rate_limiting(app)


# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/")
def root():
    """API health check"""
    return {
        "status": "healthy",
        "service": "Manufacturing KPI Platform API",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }


# ============================================================================
# AUTHENTICATION ROUTES
# ============================================================================

@app.post("/api/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(RateLimitConfig.AUTH_LIMIT)
def register_user(request: Request, user: UserCreate, db: Session = Depends(get_db)):
    """Register new user (rate limited: 10 requests/minute)"""
    # Check if username exists
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )

    # Check if email exists
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create user with generated ID
    import uuid
    user_id = f"USR-{uuid.uuid4().hex[:8].upper()}"
    hashed_password = get_password_hash(user.password)
    db_user = User(
        user_id=user_id,
        username=user.username,
        email=user.email,
        password_hash=hashed_password,
        full_name=user.full_name,
        role=user.role.upper() if user.role else "OPERATOR"
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return db_user


@app.post("/api/auth/login", response_model=Token)
@limiter.limit(RateLimitConfig.AUTH_LIMIT)
def login(request: Request, user_credentials: UserLogin, db: Session = Depends(get_db)):
    """User login (rate limited: 10 requests/minute)"""
    user = db.query(User).filter(User.username == user_credentials.username).first()

    if not user or not verify_password(user_credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    # Create access token with client_id for stateless validation (per audit requirement)
    # Include client_id_assigned in JWT payload for stateless tenant verification
    token_data = {
        "sub": user.username,
        "role": user.role,
        "client_ids": user.client_id_assigned  # Comma-separated or None for admin/poweruser
    }
    access_token = create_access_token(data=token_data)

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.from_orm(user)
    )


@app.get("/api/auth/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return current_user


# Token blacklist for logout functionality (per audit requirement)
# In production, this should be replaced with Redis or database-backed storage
_token_blacklist: set = set()


@app.post("/api/auth/logout")
def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    token: str = Depends(oauth2_scheme)
):
    """
    Explicit logout endpoint (per audit requirement)

    Invalidates the current access token by adding it to the blacklist.
    Client should also clear the token from local storage.

    Returns:
        Success message confirming logout
    """
    # Add token to blacklist (JTI would be better, using full token for simplicity)
    # In production, use Redis with TTL matching token expiration
    _token_blacklist.add(token)

    return {
        "message": "Successfully logged out",
        "detail": "Token has been invalidated. Please clear your local session."
    }


def is_token_blacklisted(token: str) -> bool:
    """Check if a token has been blacklisted (logged out)"""
    return token in _token_blacklist


@app.post("/api/auth/forgot-password")
@limiter.limit(RateLimitConfig.AUTH_LIMIT)
def forgot_password(request: Request, reset_request: PasswordResetRequest, db: Session = Depends(get_db)):
    """
    Request password reset (rate limited: 10 requests/minute)
    
    Sends a password reset email with a time-limited token.
    Always returns success to prevent email enumeration attacks.
    """
    user = db.query(User).filter(User.email == reset_request.email).first()
    
    if user and user.is_active:
        # Create password reset token (24 hour expiry)
        reset_token = create_access_token(
            data={"sub": user.username, "type": "password_reset"},
            expires_delta=timedelta(hours=24)
        )
        # TODO: Send email with reset link
        # In production, integrate with email service
        # For now, log the token (remove in production)
        print(f"[DEV] Password reset token for {user.email}: {reset_token}")
    
    # Always return success to prevent email enumeration
    return {"message": "If your email is registered, you will receive a password reset link"}


@app.post("/api/auth/reset-password")
@limiter.limit(RateLimitConfig.AUTH_LIMIT)
def reset_password(request: Request, reset_confirm: PasswordResetConfirm, db: Session = Depends(get_db)):
    """
    Reset password using token (rate limited: 10 requests/minute)
    """
    try:
        payload = jwt.decode(reset_confirm.token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username = payload.get("sub")
        token_type = payload.get("type")
        
        if token_type != "password_reset" or not username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid reset token"
            )
        
        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid reset token"
            )
        
        # Update password
        user.password_hash = get_password_hash(reset_confirm.new_password)
        user.updated_at = datetime.utcnow()
        db.commit()
        
        return {"message": "Password has been reset successfully"}
        
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )


@app.post("/api/auth/change-password")
def change_password(
    password_data: PasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Change password for authenticated user"""
    if not verify_password(password_data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    current_user.password_hash = get_password_hash(password_data.new_password)
    current_user.updated_at = datetime.utcnow()
    db.commit()
    
    return {"message": "Password changed successfully"}


# ============================================================================
# USER MANAGEMENT ROUTES (Admin)
# ============================================================================

@app.get("/api/users", response_model=List[UserResponse])
def list_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all users (admin only)"""
    if current_user.role != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    users = db.query(User).offset(skip).limit(limit).all()
    return users


@app.get("/api/users/{user_id}", response_model=UserResponse)
def get_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get user by ID (admin only)"""
    if current_user.role != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.post("/api/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create new user (admin only)"""
    if current_user.role != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    # Check if username or email already exists
    existing = db.query(User).filter(
        (User.username == user_data.username) | (User.email == user_data.email)
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered"
        )

    new_user = User(
        user_id=str(uuid.uuid4()),
        username=user_data.username,
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        role=user_data.role,
        client_id_assigned=user_data.client_id_assigned,
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@app.put("/api/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update user (admin only)"""
    if current_user.role != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = user_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == 'password' and value:
            setattr(user, 'password_hash', get_password_hash(value))
        elif hasattr(user, field):
            setattr(user, field, value)

    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    return user


@app.delete("/api/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete user (admin only)"""
    if current_user.role != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent deleting yourself
    if user.user_id == current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )

    db.delete(user)
    db.commit()


# ============================================================================
# KPI THRESHOLDS ROUTES
# ============================================================================

@app.get("/api/kpi-thresholds")
def get_kpi_thresholds(
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get KPI thresholds for a specific client or global defaults.
    If client_id is provided, returns client-specific thresholds merged with global defaults.
    If client_id is NULL/not provided, returns only global defaults.
    """
    from backend.schemas.kpi_threshold import KPIThreshold
    from backend.schemas.client import Client

    # Get global defaults
    global_thresholds = db.query(KPIThreshold).filter(
        KPIThreshold.client_id.is_(None)
    ).all()

    # Build response with global defaults
    result = {
        "client_id": client_id,
        "client_name": None,
        "thresholds": {}
    }

    # Add global defaults first
    for t in global_thresholds:
        result["thresholds"][t.kpi_key] = {
            "threshold_id": t.threshold_id,
            "kpi_key": t.kpi_key,
            "target_value": t.target_value,
            "warning_threshold": t.warning_threshold,
            "critical_threshold": t.critical_threshold,
            "unit": t.unit,
            "higher_is_better": t.higher_is_better,
            "is_global": True
        }

    # If client_id provided, override with client-specific values
    if client_id:
        client = db.query(Client).filter(Client.client_id == client_id).first()
        if client:
            result["client_name"] = client.client_name

        client_thresholds = db.query(KPIThreshold).filter(
            KPIThreshold.client_id == client_id
        ).all()

        for t in client_thresholds:
            result["thresholds"][t.kpi_key] = {
                "threshold_id": t.threshold_id,
                "kpi_key": t.kpi_key,
                "target_value": t.target_value,
                "warning_threshold": t.warning_threshold,
                "critical_threshold": t.critical_threshold,
                "unit": t.unit,
                "higher_is_better": t.higher_is_better,
                "is_global": False
            }

    return result


@app.put("/api/kpi-thresholds")
def update_kpi_thresholds(
    thresholds_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update KPI thresholds for a client or global.
    Expects: { "client_id": "xxx" or null, "thresholds": { "efficiency": { "target_value": 85 }, ... } }
    """
    if current_user.role not in ['admin', 'poweruser']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or supervisor access required"
        )

    from backend.schemas.kpi_threshold import KPIThreshold

    client_id = thresholds_data.get("client_id")
    thresholds = thresholds_data.get("thresholds", {})

    updated = []
    for kpi_key, values in thresholds.items():
        # Check if threshold exists
        existing = db.query(KPIThreshold).filter(
            KPIThreshold.client_id == client_id if client_id else KPIThreshold.client_id.is_(None),
            KPIThreshold.kpi_key == kpi_key
        ).first()

        if existing:
            # Update existing
            if "target_value" in values:
                existing.target_value = values["target_value"]
            if "warning_threshold" in values:
                existing.warning_threshold = values["warning_threshold"]
            if "critical_threshold" in values:
                existing.critical_threshold = values["critical_threshold"]
            if "unit" in values:
                existing.unit = values["unit"]
            if "higher_is_better" in values:
                existing.higher_is_better = values["higher_is_better"]
            existing.updated_at = datetime.utcnow()
            updated.append(kpi_key)
        else:
            # Create new client-specific threshold
            new_threshold = KPIThreshold(
                threshold_id=str(uuid.uuid4()),
                client_id=client_id,
                kpi_key=kpi_key,
                target_value=values.get("target_value", 0),
                warning_threshold=values.get("warning_threshold"),
                critical_threshold=values.get("critical_threshold"),
                unit=values.get("unit", "%"),
                higher_is_better=values.get("higher_is_better", "Y"),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(new_threshold)
            updated.append(kpi_key)

    db.commit()

    return {
        "message": f"Updated {len(updated)} thresholds",
        "client_id": client_id,
        "updated_kpis": updated
    }


@app.delete("/api/kpi-thresholds/{client_id}/{kpi_key}")
def delete_client_threshold(
    client_id: str,
    kpi_key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a client-specific threshold (reverts to global default).
    Cannot delete global thresholds.
    """
    if current_user.role != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    from backend.schemas.kpi_threshold import KPIThreshold

    threshold = db.query(KPIThreshold).filter(
        KPIThreshold.client_id == client_id,
        KPIThreshold.kpi_key == kpi_key
    ).first()

    if not threshold:
        raise HTTPException(status_code=404, detail="Client threshold not found")

    db.delete(threshold)
    db.commit()

    return {"message": f"Threshold {kpi_key} deleted for client {client_id}, reverted to global default"}


# ============================================================================
# PRODUCTION ENTRY ROUTES
# ============================================================================

@app.post("/api/production", response_model=ProductionEntryResponse, status_code=status.HTTP_201_CREATED)
def create_entry(
    entry: ProductionEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create new production entry"""
    # Verify product exists
    product = db.query(Product).filter(Product.product_id == entry.product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product ID {entry.product_id} not found"
        )

    # Verify shift exists
    shift = db.query(Shift).filter(Shift.shift_id == entry.shift_id).first()
    if not shift:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shift ID {entry.shift_id} not found"
        )

    return create_production_entry(db, entry, current_user)


@app.get("/api/production", response_model=List[ProductionEntryResponse])
def list_entries(
    skip: int = 0,
    limit: int = 100,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    product_id: Optional[int] = None,
    shift_id: Optional[int] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List production entries with filters"""
    return get_production_entries(
        db,
        current_user=current_user,
        skip=skip,
        limit=limit,
        start_date=start_date,
        end_date=end_date,
        product_id=product_id,
        shift_id=shift_id,
        client_id=client_id
    )


@app.get("/api/production/{entry_id}", response_model=ProductionEntryWithKPIs)
def get_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get production entry with full KPI details"""
    entry = get_production_entry_with_details(db, entry_id, current_user)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Production entry {entry_id} not found"
        )
    return entry


@app.put("/api/production/{entry_id}", response_model=ProductionEntryResponse)
def update_entry(
    entry_id: int,
    entry_update: ProductionEntryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update production entry"""
    updated_entry = update_production_entry(db, entry_id, entry_update, current_user)
    if not updated_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Production entry {entry_id} not found"
        )
    return updated_entry


@app.delete("/api/production/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor)
):
    """Delete production entry (supervisor only)"""
    success = delete_production_entry(db, entry_id, current_user)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Production entry {entry_id} not found"
        )


# ============================================================================
# KPI CALCULATION ROUTES
# ============================================================================

@app.get("/api/kpi/calculate/{entry_id}", response_model=KPICalculationResponse)
def calculate_kpis(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Calculate KPIs for a production entry"""
    entry = get_production_entry(db, entry_id, current_user)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Production entry {entry_id} not found"
        )

    product = db.query(Product).filter(Product.product_id == entry.product_id).first()

    efficiency, ideal_time, was_inferred = calculate_efficiency(db, entry, product)
    performance, _, _ = calculate_performance(db, entry, product)
    quality = calculate_quality_rate(entry)

    return KPICalculationResponse(
        entry_id=entry_id,
        efficiency_percentage=efficiency,
        performance_percentage=performance,
        quality_rate=quality,
        ideal_cycle_time_used=ideal_time,
        was_inferred=was_inferred,
        calculation_timestamp=datetime.utcnow()
    )


@app.get("/api/kpi/dashboard")
def get_kpi_dashboard(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get KPI dashboard data"""
    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()

    return get_daily_summary(db, current_user, start_date, end_date, client_id=client_id)


@app.get("/api/kpi/efficiency/by-shift")
def get_efficiency_by_shift(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get efficiency aggregated by shift"""
    from sqlalchemy import func
    from backend.schemas.production_entry import ProductionEntry
    from backend.schemas.shift import Shift

    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()

    query = db.query(
        ProductionEntry.shift_id,
        Shift.shift_name,
        func.sum(ProductionEntry.units_produced).label('actual_output'),
        func.avg(ProductionEntry.efficiency_percentage).label('efficiency'),
        func.count(ProductionEntry.production_entry_id).label('entry_count')
    ).join(
        Shift, ProductionEntry.shift_id == Shift.shift_id
    ).filter(
        ProductionEntry.shift_date >= start_date,
        ProductionEntry.shift_date <= end_date
    )

    if client_id:
        query = query.filter(ProductionEntry.client_id == client_id)

    results = query.group_by(
        ProductionEntry.shift_id,
        Shift.shift_name
    ).all()

    return [
        {
            "shift_id": r.shift_id,
            "shift_name": r.shift_name or f"Shift {r.shift_id}",
            "actual_output": r.actual_output or 0,
            "expected_output": int((r.actual_output or 0) / ((r.efficiency or 100) / 100)) if r.efficiency else 0,
            "efficiency": float(r.efficiency) if r.efficiency else 0
        }
        for r in results
    ]


@app.get("/api/kpi/efficiency/by-product")
def get_efficiency_by_product(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get top products by efficiency"""
    from sqlalchemy import func
    from backend.schemas.production_entry import ProductionEntry
    from backend.schemas.product import Product

    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()

    query = db.query(
        ProductionEntry.product_id,
        Product.product_name,
        func.sum(ProductionEntry.units_produced).label('actual_output'),
        func.avg(ProductionEntry.efficiency_percentage).label('efficiency'),
        func.count(ProductionEntry.production_entry_id).label('entry_count')
    ).join(
        Product, ProductionEntry.product_id == Product.product_id
    ).filter(
        ProductionEntry.shift_date >= start_date,
        ProductionEntry.shift_date <= end_date
    )

    if client_id:
        query = query.filter(ProductionEntry.client_id == client_id)

    results = query.group_by(
        ProductionEntry.product_id,
        Product.product_name
    ).order_by(
        func.avg(ProductionEntry.efficiency_percentage).desc()
    ).limit(limit).all()

    return [
        {
            "product_id": r.product_id,
            "product_name": r.product_name or f"Product {r.product_id}",
            "actual_output": r.actual_output or 0,
            "efficiency": float(r.efficiency) if r.efficiency else 0
        }
        for r in results
    ]


# ============================================================================
# CSV UPLOAD ROUTE
# ============================================================================

@app.post("/api/production/upload/csv", response_model=CSVUploadResponse)
async def upload_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload production entries via CSV - ALIGNED WITH PRODUCTION_ENTRY SCHEMA

    Required CSV columns:
    - client_id (str) - Multi-tenant isolation
    - product_id (int) - Product reference
    - shift_id (int) - Shift reference
    - production_date (YYYY-MM-DD) - Production date
    - units_produced (int, > 0)
    - run_time_hours (decimal)
    - employees_assigned (int)

    Optional columns:
    - shift_date (YYYY-MM-DD) - Defaults to production_date if not provided
    - work_order_id OR work_order_number (str)
    - job_id (str) - Job-level tracking
    - employees_present (int) - Actual employees present
    - defect_count (int)
    - scrap_count (int)
    - rework_count (int)
    - setup_time_hours (decimal)
    - downtime_hours (decimal)
    - maintenance_hours (decimal)
    - ideal_cycle_time (decimal)
    - notes (text)
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV"
        )

    # Read CSV
    contents = await file.read()
    csv_file = io.StringIO(contents.decode('utf-8'))
    csv_reader = csv.DictReader(csv_file)

    total_rows = 0
    successful = 0
    failed = 0
    errors = []
    created_entries = []

    for row_num, row in enumerate(csv_reader, start=2):
        total_rows += 1

        try:
            # SECURITY: Validate client_id - REQUIRED
            client_id = row.get('client_id')
            if not client_id:
                raise ValueError("client_id is required")
            from backend.middleware.client_auth import verify_client_access
            verify_client_access(current_user, client_id)

            # Parse production_date - REQUIRED
            prod_date_str = row.get('production_date')
            if not prod_date_str:
                raise ValueError("production_date is required")
            production_date = datetime.strptime(prod_date_str, '%Y-%m-%d').date()

            # Build data dict for legacy CSV mapping
            csv_data = {
                'client_id': client_id,
                'product_id': row.get('product_id'),
                'shift_id': row.get('shift_id'),
                'work_order_number': row.get('work_order_number') or row.get('work_order_id'),
                'job_id': row.get('job_id'),
                'production_date': production_date,
                'shift_date': datetime.strptime(row['shift_date'], '%Y-%m-%d').date() if row.get('shift_date') else None,
                'units_produced': row.get('units_produced'),
                'run_time_hours': row.get('run_time_hours'),
                'employees_assigned': row.get('employees_assigned'),
                'employees_present': row.get('employees_present'),
                'defect_count': row.get('defect_count', 0),
                'scrap_count': row.get('scrap_count', 0),
                'rework_count': row.get('rework_count', 0),
                'setup_time_hours': row.get('setup_time_hours'),
                'downtime_hours': row.get('downtime_hours'),
                'maintenance_hours': row.get('maintenance_hours'),
                'ideal_cycle_time': row.get('ideal_cycle_time'),
                'notes': row.get('notes')
            }

            # Use the from_legacy_csv method for proper field mapping
            entry = ProductionEntryCreate.from_legacy_csv(csv_data)

            # Create entry
            created = create_production_entry(db, entry, current_user)
            created_entries.append(created.production_entry_id)
            successful += 1

        except Exception as e:
            failed += 1
            errors.append({
                "row": row_num,
                "error": str(e),
                "data": row
            })

    return CSVUploadResponse(
        total_rows=total_rows,
        successful=successful,
        failed=failed,
        errors=errors,
        created_entries=created_entries
    )


# ============================================================================
# BATCH IMPORT ROUTE (CSV UPLOAD CONFIRMATION WORKFLOW)
# ============================================================================

@app.post("/api/production/batch-import", response_model=BatchImportResponse)
def batch_import_production(
    request: BatchImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Batch import production entries after frontend validation.

    This endpoint expects pre-validated data from the CSVUploadDialog component.
    It creates multiple production entries and logs the import for audit purposes.
    """
    total_rows = len(request.entries)
    successful = 0
    failed = 0
    errors = []
    created_entries = []

    # Process each entry
    for idx, row in enumerate(request.entries):
        try:
            # Parse and validate the entry
            entry = ProductionEntryCreate(
                product_id=int(row['product_id']),
                shift_id=int(row['shift_id']),
                production_date=row['production_date'],
                work_order_number=row.get('work_order_number') or None,
                units_produced=int(row['units_produced']),
                run_time_hours=Decimal(str(row['run_time_hours'])),
                employees_assigned=int(row['employees_assigned']),
                defect_count=int(row.get('defect_count', 0)),
                scrap_count=int(row.get('scrap_count', 0)),
                notes=row.get('notes')
            )

            # Create the entry
            created = create_production_entry(db, entry, current_user)
            created_entries.append(created.entry_id)
            successful += 1

        except Exception as e:
            failed += 1
            errors.append({
                "row": idx + 1,
                "error": str(e),
                "data": row
            })

    # Create import log entry
    import_log_id = None
    try:
        error_json = json.dumps(errors) if errors else None

        # Insert into import_log table
        result = db.execute(
            """
            INSERT INTO import_log
            (user_id, rows_attempted, rows_succeeded, rows_failed, error_details, import_type)
            VALUES (:user_id, :attempted, :succeeded, :failed, :errors, 'batch_import')
            RETURNING log_id
            """,
            {
                'user_id': current_user.user_id,
                'attempted': total_rows,
                'succeeded': successful,
                'failed': failed,
                'errors': error_json
            }
        )

        log_row = result.fetchone()
        if log_row:
            import_log_id = log_row[0]

        db.commit()

    except Exception as log_error:
        # Don't fail the entire import if logging fails
        print(f"Warning: Failed to create import log: {log_error}")
        db.rollback()

    return BatchImportResponse(
        total_rows=total_rows,
        successful=successful,
        failed=failed,
        errors=errors[:100],  # Limit error list to first 100
        created_entries=created_entries,
        import_log_id=import_log_id,
        import_timestamp=datetime.utcnow()
    )


@app.get("/api/import-logs")
def get_import_logs(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get import logs for the current user"""
    from sqlalchemy import text
    result = db.execute(
        text("""
        SELECT log_id, user_id, import_timestamp, file_name,
               rows_attempted, rows_succeeded, rows_failed,
               error_details, import_type
        FROM import_log
        WHERE user_id = :user_id
        ORDER BY import_timestamp DESC
        LIMIT :limit
        """),
        {'user_id': current_user.user_id, 'limit': limit}
    )

    logs = []
    for row in result:
        logs.append({
            'log_id': row[0],
            'user_id': row[1],
            'import_timestamp': row[2],
            'file_name': row[3],
            'rows_attempted': row[4],
            'rows_succeeded': row[5],
            'rows_failed': row[6],
            'error_details': row[7],
            'import_type': row[8]
        })

    return logs


# ============================================================================
# JOB (WORK ORDER LINE ITEMS) ROUTES - CORE DATA ENTITY
# ============================================================================

@app.post("/api/jobs", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def create_job_endpoint(
    job: JobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create new job (work order line item)
    SECURITY: Enforces client filtering
    """
    job_data = job.model_dump()
    return create_job(db, job_data, current_user)


@app.get("/api/jobs", response_model=List[JobResponse])
def list_jobs(
    work_order_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List jobs with optional work order filter
    SECURITY: Returns only jobs for user's authorized clients
    """
    return get_jobs(db, current_user, work_order_id, skip, limit)


@app.get("/api/jobs/{job_id}", response_model=JobResponse)
def get_job_endpoint(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get job by ID
    SECURITY: Verifies user has access to job's client
    """
    job = get_job(db, job_id, current_user)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or access denied")
    return job


@app.get("/api/work-orders/{work_order_id}/jobs", response_model=List[JobResponse])
def get_work_order_jobs(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all jobs for a specific work order
    SECURITY: Returns only jobs for user's authorized clients
    """
    return get_jobs_by_work_order(db, work_order_id, current_user)


@app.put("/api/jobs/{job_id}", response_model=JobResponse)
def update_job_endpoint(
    job_id: str,
    job_update: JobUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update job
    SECURITY: Verifies user has access to job's client
    """
    job_data = job_update.model_dump(exclude_unset=True)
    updated = update_job(db, job_id, job_data, current_user)
    if not updated:
        raise HTTPException(status_code=404, detail="Job not found or access denied")
    return updated


@app.post("/api/jobs/{job_id}/complete", response_model=JobResponse)
def complete_job_endpoint(
    job_id: str,
    completion: JobComplete,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Mark job as completed with actual quantities and hours
    SECURITY: Verifies user has access to job's client
    """
    completed = complete_job(
        db,
        job_id,
        completion.completed_quantity,
        float(completion.actual_hours),
        current_user
    )
    if not completed:
        raise HTTPException(status_code=404, detail="Job not found or access denied")
    return completed


@app.delete("/api/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job_endpoint(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor)
):
    """
    Delete job (supervisor only)
    SECURITY: Only deletes if user has access to job's client
    """
    success = delete_job(db, job_id, current_user)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found or access denied")


# ============================================================================
# DEFECT DETAIL ROUTES
# ============================================================================

@app.post("/api/defects", response_model=DefectDetailResponse, status_code=status.HTTP_201_CREATED)
def create_defect_endpoint(
    defect: DefectDetailCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create new defect detail record
    SECURITY: Enforces client filtering
    """
    defect_data = defect.model_dump()
    return create_defect_detail(db, defect_data, current_user)


@app.get("/api/defects", response_model=List[DefectDetailResponse])
def list_defects(
    quality_entry_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List defect details with optional quality entry filter
    SECURITY: Returns only defects for user's authorized clients
    """
    return get_defect_details(db, current_user, quality_entry_id, skip, limit)


@app.get("/api/defects/{defect_detail_id}", response_model=DefectDetailResponse)
def get_defect_endpoint(
    defect_detail_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get defect detail by ID
    SECURITY: Verifies user has access to defect's client
    """
    defect = get_defect_detail(db, defect_detail_id, current_user)
    if not defect:
        raise HTTPException(status_code=404, detail="Defect detail not found or access denied")
    return defect


@app.get("/api/quality-entries/{quality_entry_id}/defects", response_model=List[DefectDetailResponse])
def get_quality_entry_defects(
    quality_entry_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all defect details for a specific quality entry
    SECURITY: Returns only defects for user's authorized clients
    """
    return get_defect_details_by_quality_entry(db, quality_entry_id, current_user)


@app.put("/api/defects/{defect_detail_id}", response_model=DefectDetailResponse)
def update_defect_endpoint(
    defect_detail_id: str,
    defect_update: DefectDetailUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update defect detail
    SECURITY: Verifies user has access to defect's client
    """
    defect_data = defect_update.model_dump(exclude_unset=True)
    updated = update_defect_detail(db, defect_detail_id, defect_data, current_user)
    if not updated:
        raise HTTPException(status_code=404, detail="Defect detail not found or access denied")
    return updated


@app.delete("/api/defects/{defect_detail_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_defect_endpoint(
    defect_detail_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor)
):
    """
    Delete defect detail (supervisor only)
    SECURITY: Only deletes if user has access to defect's client
    """
    success = delete_defect_detail(db, defect_detail_id, current_user)
    if not success:
        raise HTTPException(status_code=404, detail="Defect detail not found or access denied")


@app.get("/api/defects/summary", response_model=List[DefectSummaryResponse])
def get_defect_summary_endpoint(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get defect summary grouped by type with optional date filtering
    SECURITY: Returns only defects for user's authorized clients
    """
    return get_defect_summary_by_type(db, current_user, start_date, end_date)


# ============================================================================
# PART_OPPORTUNITIES ROUTES (KPI #5: DPMO Calculation)
# ============================================================================

@app.post("/api/part-opportunities", response_model=PartOpportunityResponse, status_code=status.HTTP_201_CREATED)
def create_part_opportunity_endpoint(
    part: PartOpportunityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create new part opportunity record
    SECURITY: Enforces client filtering
    """
    part_data = part.model_dump()
    return create_part_opportunity(db, part_data, current_user)


@app.get("/api/part-opportunities", response_model=List[PartOpportunityResponse])
def list_part_opportunities(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List part opportunities
    SECURITY: Returns only part opportunities for user's authorized clients
    """
    return get_part_opportunities(db, current_user, skip, limit)


@app.get("/api/part-opportunities/{part_number}", response_model=PartOpportunityResponse)
def get_part_opportunity_endpoint(
    part_number: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get part opportunity by part number
    SECURITY: Verifies user has access to part's client
    """
    part = get_part_opportunity(db, part_number, current_user)
    if not part:
        raise HTTPException(status_code=404, detail="Part opportunity not found or access denied")
    return part


@app.get("/api/part-opportunities/category/{category}", response_model=List[PartOpportunityResponse])
def get_part_opportunities_by_category_endpoint(
    category: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all part opportunities for a specific category
    SECURITY: Returns only part opportunities for user's authorized clients
    """
    return get_part_opportunities_by_category(db, category, current_user)


@app.put("/api/part-opportunities/{part_number}", response_model=PartOpportunityResponse)
def update_part_opportunity_endpoint(
    part_number: str,
    part_update: PartOpportunityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update part opportunity
    SECURITY: Verifies user has access to part's client
    """
    part_data = part_update.model_dump(exclude_unset=True)
    updated = update_part_opportunity(db, part_number, part_data, current_user)
    if not updated:
        raise HTTPException(status_code=404, detail="Part opportunity not found or access denied")
    return updated


@app.delete("/api/part-opportunities/{part_number}", status_code=status.HTTP_204_NO_CONTENT)
def delete_part_opportunity_endpoint(
    part_number: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor)
):
    """
    Delete part opportunity (supervisor only)
    SECURITY: Only deletes if user has access to part's client
    """
    success = delete_part_opportunity(db, part_number, current_user)
    if not success:
        raise HTTPException(status_code=404, detail="Part opportunity not found or access denied")


@app.post("/api/part-opportunities/bulk-import", response_model=BulkImportResponse)
def bulk_import_part_opportunities(
    import_request: BulkImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Bulk import part opportunities (for CSV imports)
    SECURITY: Validates client_id_fk for all records
    """
    opportunities_list = [opp.model_dump() for opp in import_request.opportunities]
    result = bulk_import_opportunities(db, opportunities_list, current_user)

    return BulkImportResponse(
        success_count=result["success_count"],
        failure_count=result["failure_count"],
        errors=result["errors"],
        total_processed=result["success_count"] + result["failure_count"]
    )


# ============================================================================
# REPORT GENERATION ROUTES
# ============================================================================

@app.get("/api/reports/daily/{report_date}")
def generate_daily_pdf_report(
    report_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate daily production PDF report"""
    from backend.reports.pdf_generator import PDFReportGenerator

    pdf_generator = PDFReportGenerator(db)
    pdf_buffer = pdf_generator.generate_report(
        client_id=None,
        start_date=report_date,
        end_date=report_date
    )

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=daily_report_{report_date}.pdf"
        }
    )


# ============================================================================
# REFERENCE DATA ROUTES
# ============================================================================

@app.get("/api/products", response_model=List[dict])
def list_products(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all active products (authentication required)"""
    products = db.query(Product).filter(Product.is_active == True).all()
    return [
        {
            "product_id": p.product_id,
            "product_code": p.product_code,
            "product_name": p.product_name,
            "ideal_cycle_time": float(p.ideal_cycle_time) if p.ideal_cycle_time else None
        }
        for p in products
    ]


@app.get("/api/shifts", response_model=List[dict])
def list_shifts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all active shifts (authentication required)"""
    shifts = db.query(Shift).filter(Shift.is_active == True).all()
    return [
        {
            "shift_id": s.shift_id,
            "shift_name": s.shift_name,
            "start_time": s.start_time.strftime("%H:%M"),
            "end_time": s.end_time.strftime("%H:%M")
        }
        for s in shifts
    ]


# ============================================================================
# PHASE 2: DOWNTIME TRACKING ROUTES
# ============================================================================

@app.post("/api/downtime", response_model=DowntimeEventResponse, status_code=status.HTTP_201_CREATED)
def create_downtime(
    downtime: DowntimeEventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create downtime event"""
    return create_downtime_event(db, downtime, current_user)


@app.get("/api/downtime", response_model=List[DowntimeEventResponse])
def list_downtime(
    skip: int = 0,
    limit: int = 100,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    work_order_id: Optional[str] = None,
    downtime_reason: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List downtime events with filters"""
    return get_downtime_events(
        db, current_user=current_user, skip=skip, limit=limit, start_date=start_date,
        end_date=end_date, client_id=client_id, work_order_id=work_order_id,
        downtime_reason=downtime_reason
    )


@app.get("/api/downtime/{downtime_id}", response_model=DowntimeEventResponse)
def get_downtime(
    downtime_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get downtime event by ID"""
    event = get_downtime_event(db, downtime_id, current_user)
    if not event:
        raise HTTPException(status_code=404, detail="Downtime event not found")
    return event


@app.put("/api/downtime/{downtime_id}", response_model=DowntimeEventResponse)
def update_downtime(
    downtime_id: str,
    downtime_update: DowntimeEventUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update downtime event"""
    updated = update_downtime_event(db, downtime_id, downtime_update, current_user)
    if not updated:
        raise HTTPException(status_code=404, detail="Downtime event not found")
    return updated


@app.delete("/api/downtime/{downtime_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_downtime(
    downtime_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor)
):
    """Delete downtime event (supervisor only)"""
    success = delete_downtime_event(db, downtime_id, current_user)
    if not success:
        raise HTTPException(status_code=404, detail="Downtime event not found")


@app.get("/api/kpi/availability", response_model=AvailabilityCalculationResponse)
def calculate_availability_kpi(
    product_id: int,
    shift_id: int,
    production_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Calculate availability KPI"""
    availability, scheduled, downtime, events = calculate_availability(
        db, product_id, shift_id, production_date
    )

    return AvailabilityCalculationResponse(
        product_id=product_id,
        shift_id=shift_id,
        production_date=production_date,
        total_scheduled_hours=scheduled,
        total_downtime_hours=downtime,
        available_hours=scheduled - downtime,
        availability_percentage=availability,
        downtime_events=events,
        calculation_timestamp=datetime.utcnow()
    )


# ============================================================================
# PHASE 2: WIP HOLD TRACKING ROUTES
# ============================================================================

@app.post("/api/holds", response_model=WIPHoldResponse, status_code=status.HTTP_201_CREATED)
def create_hold(
    hold: WIPHoldCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create WIP hold record"""
    return create_wip_hold(db, hold, current_user)


@app.get("/api/holds", response_model=List[WIPHoldResponse])
def list_holds(
    skip: int = 0,
    limit: int = 100,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    work_order_id: Optional[str] = None,
    released: Optional[bool] = None,
    hold_reason_category: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List WIP holds with filters - uses HOLD_ENTRY schema"""
    return get_wip_holds(
        db, current_user=current_user, skip=skip, limit=limit, start_date=start_date,
        end_date=end_date, client_id=client_id, work_order_id=work_order_id,
        released=released, hold_reason_category=hold_reason_category
    )


@app.get("/api/holds/{hold_id}", response_model=WIPHoldResponse)
def get_hold(
    hold_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get WIP hold by ID"""
    hold = get_wip_hold(db, hold_id, current_user)
    if not hold:
        raise HTTPException(status_code=404, detail="WIP hold not found")
    return hold


@app.put("/api/holds/{hold_id}", response_model=WIPHoldResponse)
def update_hold(
    hold_id: int,
    hold_update: WIPHoldUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update WIP hold record"""
    updated = update_wip_hold(db, hold_id, hold_update, current_user)
    if not updated:
        raise HTTPException(status_code=404, detail="WIP hold not found")
    return updated


@app.delete("/api/holds/{hold_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_hold(
    hold_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor)
):
    """Delete WIP hold (supervisor only)"""
    success = delete_wip_hold(db, hold_id, current_user)
    if not success:
        raise HTTPException(status_code=404, detail="WIP hold not found")


@app.get("/api/kpi/wip-aging", response_model=WIPAgingResponse)
def calculate_wip_aging_kpi(
    product_id: Optional[int] = None,
    as_of_date: Optional[date] = None,
    client_id: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Calculate WIP aging analysis with client filtering"""
    from backend.schemas.hold_entry import HoldEntry, HoldStatus

    # Determine effective client filter
    effective_client_id = client_id
    if not effective_client_id and current_user.role != 'admin' and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    # Build query for hold entries - only active holds
    query = db.query(HoldEntry).filter(HoldEntry.hold_status == HoldStatus.ON_HOLD)

    # Apply client filter
    if effective_client_id:
        query = query.filter(HoldEntry.client_id == effective_client_id)

    # Apply date filters if provided (on hold_date)
    if start_date:
        query = query.filter(HoldEntry.hold_date >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        query = query.filter(HoldEntry.hold_date <= datetime.combine(end_date, datetime.max.time()))

    # Get all active holds
    holds = query.all()

    # Calculate aging metrics
    calculation_date = as_of_date or date.today()
    total_held = len(holds)
    total_age = 0
    aging_0_7 = 0
    aging_8_14 = 0
    aging_15_30 = 0
    aging_over_30 = 0

    for hold in holds:
        # Properly convert DateTime to date for comparison
        hold_date = hold.hold_date
        if hold_date is None:
            continue

        # Handle both datetime and date types, and string from SQLite
        if hasattr(hold_date, 'date'):
            hold_date = hold_date.date()
        elif isinstance(hold_date, str):
            # Parse date string from SQLite
            hold_date = datetime.strptime(hold_date.split()[0], '%Y-%m-%d').date()

        age_days = (calculation_date - hold_date).days
        total_age += age_days

        if age_days <= 7:
            aging_0_7 += 1
        elif age_days <= 14:
            aging_8_14 += 1
        elif age_days <= 30:
            aging_15_30 += 1
        else:
            aging_over_30 += 1

    avg_aging = total_age / total_held if total_held > 0 else 0

    return WIPAgingResponse(
        total_held_quantity=total_held,
        average_aging_days=round(avg_aging, 1),
        aging_0_7_days=aging_0_7,
        aging_8_14_days=aging_8_14,
        aging_15_30_days=aging_15_30,
        aging_over_30_days=aging_over_30,
        total_hold_events=total_held,
        calculation_timestamp=datetime.utcnow()
    )


@app.get("/api/kpi/wip-aging/top")
def get_top_aging_items(
    limit: int = 10,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get top aging WIP items - for WIP Aging view table"""
    from backend.schemas.hold_entry import HoldEntry, HoldStatus
    from backend.schemas.work_order import WorkOrder
    from sqlalchemy import func

    query = db.query(
        HoldEntry.work_order_id,
        WorkOrder.style_model,
        HoldEntry.hold_date,
        func.julianday('now') - func.julianday(HoldEntry.hold_date)
    ).outerjoin(
        WorkOrder, HoldEntry.work_order_id == WorkOrder.work_order_id
    ).filter(
        HoldEntry.hold_status == HoldStatus.ON_HOLD
    )

    # Apply client filter
    if client_id:
        query = query.filter(HoldEntry.client_id == client_id)
    elif current_user.role != 'admin' and current_user.client_id_assigned:
        query = query.filter(HoldEntry.client_id == current_user.client_id_assigned)

    results = query.order_by(
        (func.julianday('now') - func.julianday(HoldEntry.hold_date)).desc()
    ).limit(limit).all()

    return [
        {
            "work_order": r[0],
            "product": r[1] or "N/A",
            "age": int(r[3]) if r[3] else 0,
            "quantity": 1  # Placeholder - HOLD_ENTRY doesn't track quantity
        }
        for r in results
    ]


@app.get("/api/kpi/wip-aging/trend")
def get_wip_aging_trend(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get WIP aging trend data - for WIP Aging view chart"""
    from backend.schemas.hold_entry import HoldEntry, HoldStatus
    from sqlalchemy import func, cast, Date

    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()

    # Get daily average aging for the date range
    # We calculate for each day how old the active holds were on that day
    trend_data = []
    current_date = start_date

    while current_date <= end_date:
        # Query holds that were active on this date
        query = db.query(
            func.avg(func.julianday(current_date) - func.julianday(HoldEntry.hold_date))
        ).filter(
            HoldEntry.hold_date <= current_date,
            (HoldEntry.resume_date.is_(None)) | (HoldEntry.resume_date > current_date)
        )

        # Apply client filter
        if client_id:
            query = query.filter(HoldEntry.client_id == client_id)
        elif current_user.role != 'admin' and current_user.client_id_assigned:
            query = query.filter(HoldEntry.client_id == current_user.client_id_assigned)

        result = query.scalar()
        avg_age = float(result) if result else 0

        trend_data.append({
            "date": current_date.isoformat(),
            "value": round(avg_age, 1)
        })

        current_date += timedelta(days=1)

    return trend_data


@app.get("/api/kpi/chronic-holds")
def get_chronic_holds(
    threshold_days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Identify chronic WIP holds"""
    return identify_chronic_holds(db, threshold_days)


# ============================================================================
# PHASE 3 & 4: MODULAR ROUTE REGISTRATION
# Routes moved to /backend/routes/ modules for better organization
# ============================================================================

# Import and register modular route modules
from backend.routes import (
    attendance_router,
    coverage_router,
    quality_router,
    defect_router,
    analytics_router,
    predictions_router,
    qr_router,
    preferences_router,
    filters_router
)

# Import reports router
from backend.routes.reports import router as reports_router
from backend.routes.health import router as health_router
from backend.routes.defect_type_catalog import router as defect_type_catalog_router

# Import CSV upload endpoints
from backend.endpoints.csv_upload import router as csv_upload_router

# Register health check and monitoring routes
app.include_router(health_router)

# Register CSV upload routes for all resources
app.include_router(csv_upload_router)

# Register attendance tracking routes
app.include_router(attendance_router)

# Register shift coverage routes
app.include_router(coverage_router)

# Register quality inspection routes
app.include_router(quality_router)

# Register defect detail routes
app.include_router(defect_router)

# Register comprehensive report generation routes
app.include_router(reports_router)

# Register analytics and prediction routes
app.include_router(analytics_router)

# Phase 5: Register comprehensive predictions routes
app.include_router(predictions_router)

# Phase 6: Register QR code routes
app.include_router(qr_router)

# Phase 7: Register user preferences routes
app.include_router(preferences_router)

# Phase 8: Register saved filters routes
app.include_router(filters_router)

# Phase 9: Register defect type catalog routes (client-specific defect types)
app.include_router(defect_type_catalog_router)

# OTD (On-Time Delivery) KPI endpoints remain in main.py
# as they don't fit into the modular structure
@app.get("/api/kpi/otd")
def calculate_otd_kpi(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Calculate On-Time Delivery KPI with client filtering

    OTD = (Orders Delivered On Time / Total Orders with Due Dates) × 100
    Uses required_date as the due date and actual_delivery_date for completion.
    Parameters are optional - defaults to last 30 days.
    """
    from datetime import timedelta
    from backend.schemas.work_order import WorkOrder

    # Default to last 30 days if dates not provided
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    # Determine effective client filter
    effective_client_id = client_id
    if not effective_client_id and current_user.role != 'admin' and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    # Build query with client filter - use required_date as the due date
    query = db.query(WorkOrder).filter(
        WorkOrder.required_date.isnot(None),
        WorkOrder.required_date >= datetime.combine(start_date, datetime.min.time()),
        WorkOrder.required_date <= datetime.combine(end_date, datetime.max.time())
    )

    # Apply client filter
    if effective_client_id:
        query = query.filter(WorkOrder.client_id == effective_client_id)

    work_orders = query.all()

    # Calculate OTD metrics
    total_orders = len(work_orders)
    on_time_count = 0

    for wo in work_orders:
        # Get the due date (required_date)
        due_date = wo.required_date
        if hasattr(due_date, 'date'):
            due_date = due_date.date()

        # Consider on-time if delivered by due date or still open before due date
        if wo.actual_delivery_date:
            delivery_date = wo.actual_delivery_date
            if hasattr(delivery_date, 'date'):
                delivery_date = delivery_date.date()
            if delivery_date <= due_date:
                on_time_count += 1
        elif due_date >= date.today():
            # Still open and not past due
            on_time_count += 1

    otd_percentage = (on_time_count / total_orders * 100) if total_orders > 0 else 0

    return {
        "start_date": start_date,
        "end_date": end_date,
        "client_id": effective_client_id,
        "otd_percentage": round(otd_percentage, 2),
        "on_time_count": on_time_count,
        "total_orders": total_orders,
        "calculation_timestamp": datetime.utcnow()
    }


@app.get("/api/kpi/late-orders")
def get_late_orders(
    as_of_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Identify late orders"""
    return identify_late_orders(db, as_of_date or date.today())


@app.get("/api/kpi/otd/by-client")
def get_otd_by_client(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get OTD metrics aggregated by client"""
    from sqlalchemy import func, case
    from backend.schemas.work_order import WorkOrder
    from backend.schemas.client import Client

    # Default to last 30 days if dates not provided
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    # Query work orders grouped by client
    query = db.query(
        WorkOrder.client_id,
        Client.client_name,
        func.count(WorkOrder.work_order_id).label('total_deliveries'),
        func.sum(
            case(
                (WorkOrder.actual_delivery_date <= WorkOrder.required_date, 1),
                (WorkOrder.actual_delivery_date.is_(None),
                 case((WorkOrder.required_date >= date.today(), 1), else_=0)),
                else_=0
            )
        ).label('on_time')
    ).join(
        Client, WorkOrder.client_id == Client.client_id
    ).filter(
        WorkOrder.required_date.isnot(None),
        WorkOrder.required_date >= datetime.combine(start_date, datetime.min.time()),
        WorkOrder.required_date <= datetime.combine(end_date, datetime.max.time())
    )

    # Non-admin users only see their assigned client
    if current_user.role != 'admin' and current_user.client_id_assigned:
        query = query.filter(WorkOrder.client_id == current_user.client_id_assigned)

    results = query.group_by(
        WorkOrder.client_id,
        Client.client_name
    ).all()

    return [
        {
            "client_id": r.client_id,
            "client_name": r.client_name or f"Client {r.client_id}",
            "total_deliveries": r.total_deliveries or 0,
            "on_time": r.on_time or 0,
            "otd_percentage": round((r.on_time / r.total_deliveries * 100) if r.total_deliveries > 0 else 0, 1)
        }
        for r in results
    ]


@app.get("/api/kpi/otd/late-deliveries")
def get_late_deliveries(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get recent late deliveries with details"""
    from backend.schemas.work_order import WorkOrder
    from backend.schemas.client import Client

    # Default to last 30 days if dates not provided
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    # Determine effective client filter
    effective_client_id = client_id
    if not effective_client_id and current_user.role != 'admin' and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    # Query for late deliveries (actual_delivery_date > required_date)
    query = db.query(
        WorkOrder.work_order_id,
        WorkOrder.client_id,
        Client.client_name,
        WorkOrder.required_date,
        WorkOrder.actual_delivery_date,
        WorkOrder.style_model
    ).join(
        Client, WorkOrder.client_id == Client.client_id
    ).filter(
        WorkOrder.required_date.isnot(None),
        WorkOrder.actual_delivery_date.isnot(None),
        WorkOrder.actual_delivery_date > WorkOrder.required_date,
        WorkOrder.actual_delivery_date >= datetime.combine(start_date, datetime.min.time()),
        WorkOrder.actual_delivery_date <= datetime.combine(end_date, datetime.max.time())
    )

    # Apply client filter
    if effective_client_id:
        query = query.filter(WorkOrder.client_id == effective_client_id)

    # Order by delivery date (most recent first) and limit
    results = query.order_by(WorkOrder.actual_delivery_date.desc()).limit(limit).all()

    late_deliveries = []
    for r in results:
        # Calculate delay in hours
        required = r.required_date
        actual = r.actual_delivery_date

        # Handle datetime vs date conversion
        if hasattr(required, 'date'):
            required_dt = required
        else:
            required_dt = datetime.combine(required, datetime.min.time())

        if hasattr(actual, 'date'):
            actual_dt = actual
        else:
            actual_dt = datetime.combine(actual, datetime.min.time())

        delay_hours = int((actual_dt - required_dt).total_seconds() / 3600)

        late_deliveries.append({
            "delivery_date": str(actual.date() if hasattr(actual, 'date') else actual),
            "work_order": r.work_order_id,
            "client": r.client_name or r.client_id,
            "delay_hours": delay_hours,
            "style_model": r.style_model
        })

    return late_deliveries


# ============================================================================
# KPI TREND ENDPOINTS
# ============================================================================

@app.get("/api/kpi/efficiency/trend")
def get_efficiency_trend(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get daily efficiency trend data"""
    from datetime import timedelta
    from backend.schemas.production_entry import ProductionEntry
    from sqlalchemy import func

    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    effective_client_id = client_id
    if not effective_client_id and current_user.role != 'admin' and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    query = db.query(
        func.date(ProductionEntry.shift_date).label('date'),
        func.avg(ProductionEntry.efficiency_percentage).label('value')
    ).filter(
        ProductionEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
        ProductionEntry.shift_date <= datetime.combine(end_date, datetime.max.time())
    )

    if effective_client_id:
        query = query.filter(ProductionEntry.client_id == effective_client_id)

    results = query.group_by(func.date(ProductionEntry.shift_date)).order_by(func.date(ProductionEntry.shift_date)).all()

    return [{"date": str(r.date), "value": round(float(r.value), 2) if r.value else 0} for r in results]


@app.get("/api/kpi/performance/trend")
def get_performance_trend(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get daily performance trend data"""
    from datetime import timedelta
    from backend.schemas.production_entry import ProductionEntry
    from sqlalchemy import func

    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    effective_client_id = client_id
    if not effective_client_id and current_user.role != 'admin' and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    query = db.query(
        func.date(ProductionEntry.shift_date).label('date'),
        func.avg(ProductionEntry.performance_percentage).label('value')
    ).filter(
        ProductionEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
        ProductionEntry.shift_date <= datetime.combine(end_date, datetime.max.time())
    )

    if effective_client_id:
        query = query.filter(ProductionEntry.client_id == effective_client_id)

    results = query.group_by(func.date(ProductionEntry.shift_date)).order_by(func.date(ProductionEntry.shift_date)).all()

    return [{"date": str(r.date), "value": round(float(r.value), 2) if r.value else 0} for r in results]


@app.get("/api/kpi/performance/by-shift")
def get_performance_by_shift(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get performance aggregated by shift"""
    from sqlalchemy import func
    from backend.schemas.production_entry import ProductionEntry
    from backend.schemas.shift import Shift

    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()

    effective_client_id = client_id
    if not effective_client_id and current_user.role != 'admin' and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    query = db.query(
        ProductionEntry.shift_id,
        Shift.shift_name,
        func.sum(ProductionEntry.units_produced).label('units'),
        func.sum(ProductionEntry.run_time_hours).label('hours'),
        func.avg(ProductionEntry.performance_percentage).label('performance'),
        func.count(ProductionEntry.production_entry_id).label('entry_count')
    ).outerjoin(
        Shift, ProductionEntry.shift_id == Shift.shift_id
    ).filter(
        ProductionEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
        ProductionEntry.shift_date <= datetime.combine(end_date, datetime.max.time())
    )

    if effective_client_id:
        query = query.filter(ProductionEntry.client_id == effective_client_id)

    results = query.group_by(
        ProductionEntry.shift_id,
        Shift.shift_name
    ).order_by(
        func.avg(ProductionEntry.performance_percentage).desc()
    ).all()

    return [
        {
            "shift_id": r.shift_id,
            "shift_name": r.shift_name or f"Shift {r.shift_id}",
            "units": int(r.units) if r.units else 0,
            "rate": round(float(r.units) / float(r.hours), 1) if r.hours and r.hours > 0 else 0,
            "performance": round(float(r.performance), 1) if r.performance else 0
        }
        for r in results
    ]


@app.get("/api/kpi/performance/by-product")
def get_performance_by_product(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get performance aggregated by product"""
    from sqlalchemy import func
    from backend.schemas.production_entry import ProductionEntry
    from backend.schemas.product import Product

    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()

    effective_client_id = client_id
    if not effective_client_id and current_user.role != 'admin' and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    query = db.query(
        ProductionEntry.product_id,
        Product.product_name,
        func.sum(ProductionEntry.units_produced).label('units'),
        func.sum(ProductionEntry.run_time_hours).label('hours'),
        func.avg(ProductionEntry.performance_percentage).label('performance'),
        func.count(ProductionEntry.production_entry_id).label('entry_count')
    ).join(
        Product, ProductionEntry.product_id == Product.product_id
    ).filter(
        ProductionEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
        ProductionEntry.shift_date <= datetime.combine(end_date, datetime.max.time())
    )

    if effective_client_id:
        query = query.filter(ProductionEntry.client_id == effective_client_id)

    results = query.group_by(
        ProductionEntry.product_id,
        Product.product_name
    ).order_by(
        func.avg(ProductionEntry.performance_percentage).desc()
    ).limit(limit).all()

    return [
        {
            "product_id": r.product_id,
            "product_name": r.product_name or f"Product {r.product_id}",
            "units": int(r.units) if r.units else 0,
            "rate": round(float(r.units) / float(r.hours), 1) if r.hours and r.hours > 0 else 0,
            "performance": round(float(r.performance), 1) if r.performance else 0
        }
        for r in results
    ]


@app.get("/api/kpi/quality/trend")
def get_quality_trend(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get daily quality (FPY) trend data"""
    from datetime import timedelta
    from backend.schemas.quality_entry import QualityEntry
    from sqlalchemy import func

    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    effective_client_id = client_id
    if not effective_client_id and current_user.role != 'admin' and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    query = db.query(
        func.date(QualityEntry.shift_date).label('date'),
        func.sum(QualityEntry.units_passed).label('passed'),
        func.sum(QualityEntry.units_inspected).label('inspected')
    ).filter(
        QualityEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
        QualityEntry.shift_date <= datetime.combine(end_date, datetime.max.time())
    )

    if effective_client_id:
        query = query.filter(QualityEntry.client_id == effective_client_id)

    results = query.group_by(func.date(QualityEntry.shift_date)).order_by(func.date(QualityEntry.shift_date)).all()

    return [
        {
            "date": str(r.date),
            "value": round((r.passed / r.inspected) * 100, 2) if r.inspected and r.inspected > 0 else 0
        }
        for r in results
    ]


@app.get("/api/kpi/availability/trend")
def get_availability_trend(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get daily availability trend data (calculated from downtime)"""
    from datetime import timedelta
    from backend.schemas.downtime_entry import DowntimeEntry
    from backend.schemas.production_entry import ProductionEntry
    from sqlalchemy import func

    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    effective_client_id = client_id
    if not effective_client_id and current_user.role != 'admin' and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    # Get production days (scheduled time proxy)
    prod_query = db.query(
        func.date(ProductionEntry.shift_date).label('date'),
        func.count(ProductionEntry.production_entry_id).label('entries')
    ).filter(
        ProductionEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
        ProductionEntry.shift_date <= datetime.combine(end_date, datetime.max.time())
    )
    if effective_client_id:
        prod_query = prod_query.filter(ProductionEntry.client_id == effective_client_id)
    prod_results = {str(r.date): r.entries * 8 for r in prod_query.group_by(func.date(ProductionEntry.shift_date)).all()}

    # Get downtime by day
    dt_query = db.query(
        func.date(DowntimeEntry.shift_date).label('date'),
        func.sum(DowntimeEntry.downtime_duration_minutes).label('downtime_mins')
    ).filter(
        DowntimeEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
        DowntimeEntry.shift_date <= datetime.combine(end_date, datetime.max.time())
    )
    if effective_client_id:
        dt_query = dt_query.filter(DowntimeEntry.client_id == effective_client_id)
    dt_results = {str(r.date): float(r.downtime_mins) / 60 if r.downtime_mins else 0 for r in dt_query.group_by(func.date(DowntimeEntry.shift_date)).all()}

    # Calculate availability per day
    trend_data = []
    for day in sorted(prod_results.keys()):
        scheduled = prod_results.get(day, 8)
        downtime = dt_results.get(day, 0)
        availability = ((scheduled - downtime) / scheduled * 100) if scheduled > 0 else 100
        trend_data.append({"date": day, "value": round(max(0, min(100, availability)), 2)})

    return trend_data


@app.get("/api/kpi/oee/trend")
def get_oee_trend(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get daily OEE trend data (Availability × Performance × Quality)"""
    from datetime import timedelta
    from backend.schemas.production_entry import ProductionEntry
    from backend.schemas.quality_entry import QualityEntry
    from backend.schemas.downtime_entry import DowntimeEntry
    from sqlalchemy import func

    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    effective_client_id = client_id
    if not effective_client_id and current_user.role != 'admin' and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    # Get performance by day
    perf_query = db.query(
        func.date(ProductionEntry.shift_date).label('date'),
        func.avg(ProductionEntry.performance_percentage).label('performance'),
        func.count(ProductionEntry.production_entry_id).label('entries')
    ).filter(
        ProductionEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
        ProductionEntry.shift_date <= datetime.combine(end_date, datetime.max.time())
    )
    if effective_client_id:
        perf_query = perf_query.filter(ProductionEntry.client_id == effective_client_id)
    perf_results = {str(r.date): {"performance": float(r.performance) if r.performance else 95, "entries": r.entries} for r in perf_query.group_by(func.date(ProductionEntry.shift_date)).all()}

    # Get quality by day
    qual_query = db.query(
        func.date(QualityEntry.shift_date).label('date'),
        func.sum(QualityEntry.units_passed).label('passed'),
        func.sum(QualityEntry.units_inspected).label('inspected')
    ).filter(
        QualityEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
        QualityEntry.shift_date <= datetime.combine(end_date, datetime.max.time())
    )
    if effective_client_id:
        qual_query = qual_query.filter(QualityEntry.client_id == effective_client_id)
    qual_results = {str(r.date): (r.passed / r.inspected * 100) if r.inspected and r.inspected > 0 else 97 for r in qual_query.group_by(func.date(QualityEntry.shift_date)).all()}

    # Get downtime by day
    dt_query = db.query(
        func.date(DowntimeEntry.shift_date).label('date'),
        func.sum(DowntimeEntry.downtime_duration_minutes).label('downtime_mins')
    ).filter(
        DowntimeEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
        DowntimeEntry.shift_date <= datetime.combine(end_date, datetime.max.time())
    )
    if effective_client_id:
        dt_query = dt_query.filter(DowntimeEntry.client_id == effective_client_id)
    dt_results = {str(r.date): float(r.downtime_mins) / 60 if r.downtime_mins else 0 for r in dt_query.group_by(func.date(DowntimeEntry.shift_date)).all()}

    # Calculate OEE per day
    trend_data = []
    for day in sorted(perf_results.keys()):
        scheduled = perf_results[day]["entries"] * 8
        downtime = dt_results.get(day, 0)
        availability = ((scheduled - downtime) / scheduled * 100) if scheduled > 0 else 90
        performance = perf_results[day]["performance"]
        quality = qual_results.get(day, 97)
        oee = (availability / 100) * (performance / 100) * (quality / 100) * 100
        trend_data.append({"date": day, "value": round(min(100, oee), 2)})

    return trend_data


@app.get("/api/kpi/on-time-delivery/trend")
def get_otd_trend(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get daily On-Time Delivery trend data"""
    from datetime import timedelta
    from backend.schemas.work_order import WorkOrder
    from sqlalchemy import func, case

    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    effective_client_id = client_id
    if not effective_client_id and current_user.role != 'admin' and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    # Query work orders grouped by required_date
    query = db.query(
        func.date(WorkOrder.required_date).label('date'),
        func.count(WorkOrder.work_order_id).label('total'),
        func.sum(
            case(
                (WorkOrder.actual_delivery_date <= WorkOrder.required_date, 1),
                else_=0
            )
        ).label('on_time')
    ).filter(
        WorkOrder.required_date.isnot(None),
        WorkOrder.required_date >= datetime.combine(start_date, datetime.min.time()),
        WorkOrder.required_date <= datetime.combine(end_date, datetime.max.time())
    )

    if effective_client_id:
        query = query.filter(WorkOrder.client_id == effective_client_id)

    results = query.group_by(func.date(WorkOrder.required_date)).order_by(func.date(WorkOrder.required_date)).all()

    return [{"date": str(r.date), "value": round((r.on_time / r.total * 100) if r.total > 0 else 0, 2)} for r in results]


@app.get("/api/kpi/absenteeism/trend")
def get_absenteeism_trend(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get daily absenteeism trend data"""
    from datetime import timedelta
    from backend.schemas.attendance_entry import AttendanceEntry
    from sqlalchemy import func

    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    effective_client_id = client_id
    if not effective_client_id and current_user.role != 'admin' and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    # Query attendance grouped by shift_date
    query = db.query(
        func.date(AttendanceEntry.shift_date).label('date'),
        func.sum(AttendanceEntry.scheduled_hours).label('scheduled'),
        func.sum(func.coalesce(AttendanceEntry.absence_hours, 0)).label('absent')
    ).filter(
        AttendanceEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
        AttendanceEntry.shift_date <= datetime.combine(end_date, datetime.max.time())
    )

    if effective_client_id:
        query = query.filter(AttendanceEntry.client_id == effective_client_id)

    results = query.group_by(func.date(AttendanceEntry.shift_date)).order_by(func.date(AttendanceEntry.shift_date)).all()

    return [{"date": str(r.date), "value": round((r.absent / r.scheduled * 100) if r.scheduled and r.scheduled > 0 else 0, 2)} for r in results]


# ============================================================================
# WORK ORDER ROUTES (SPRINT 1)
# ============================================================================

@app.post("/api/work-orders", response_model=WorkOrderResponse, status_code=status.HTTP_201_CREATED)
def create_work_order_endpoint(
    work_order: WorkOrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create new work order
    SECURITY: Enforces client filtering
    """
    work_order_data = work_order.model_dump()
    return create_work_order(db, work_order_data, current_user)


@app.get("/api/work-orders", response_model=List[WorkOrderResponse])
def list_work_orders(
    skip: int = 0,
    limit: int = 100,
    client_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    style_model: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List work orders with filters
    SECURITY: Returns only work orders for user's authorized clients
    """
    return get_work_orders(db, current_user, skip, limit, client_id, status_filter, style_model)


@app.get("/api/work-orders/{work_order_id}", response_model=WorkOrderResponse)
def get_work_order_endpoint(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get work order by ID
    SECURITY: Verifies user has access to work order's client
    """
    work_order = get_work_order(db, work_order_id, current_user)
    if not work_order:
        raise HTTPException(status_code=404, detail="Work order not found or access denied")
    return work_order


@app.put("/api/work-orders/{work_order_id}", response_model=WorkOrderResponse)
def update_work_order_endpoint(
    work_order_id: str,
    work_order_update: WorkOrderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update work order
    SECURITY: Verifies user has access to work order's client
    """
    work_order_data = work_order_update.model_dump(exclude_unset=True)
    updated = update_work_order(db, work_order_id, work_order_data, current_user)
    if not updated:
        raise HTTPException(status_code=404, detail="Work order not found or access denied")
    return updated


@app.delete("/api/work-orders/{work_order_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_work_order_endpoint(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor)
):
    """
    Delete work order (supervisor only)
    SECURITY: Only deletes if user has access to work order's client
    """
    success = delete_work_order(db, work_order_id, current_user)
    if not success:
        raise HTTPException(status_code=404, detail="Work order not found or access denied")


@app.get("/api/clients/{client_id}/work-orders", response_model=List[WorkOrderResponse])
def get_client_work_orders(
    client_id: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all work orders for a specific client
    SECURITY: Returns only work orders for user's authorized clients
    """
    return get_work_orders_by_client(db, client_id, current_user, skip, limit)


@app.get("/api/work-orders/status/{status}", response_model=List[WorkOrderResponse])
def get_work_orders_by_status_endpoint(
    status: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get work orders by status
    SECURITY: Returns only work orders for user's authorized clients
    """
    return get_work_orders_by_status(db, status, current_user, skip, limit)


@app.get("/api/work-orders/date-range", response_model=List[WorkOrderResponse])
def get_work_orders_by_date_range_endpoint(
    start_date: datetime,
    end_date: datetime,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get work orders within date range
    SECURITY: Returns only work orders for user's authorized clients
    """
    return get_work_orders_by_date_range(db, start_date, end_date, current_user, skip, limit)


# ============================================================================
# CLIENT ROUTES (SPRINT 1)
# ============================================================================

@app.post("/api/clients", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
def create_client_endpoint(
    client: ClientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create new client
    SECURITY: Admin only
    """
    client_data = client.model_dump()
    return create_client(db, client_data, current_user)


@app.get("/api/clients", response_model=List[ClientResponse])
def list_clients(
    skip: int = 0,
    limit: int = 100,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List clients with filters
    SECURITY: Returns only clients user has access to
    """
    return get_clients(db, current_user, skip, limit, is_active)


@app.get("/api/clients/{client_id}", response_model=ClientResponse)
def get_client_endpoint(
    client_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get client by ID
    SECURITY: Verifies user has access to client
    """
    client = get_client(db, client_id, current_user)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found or access denied")
    return client


@app.put("/api/clients/{client_id}", response_model=ClientResponse)
def update_client_endpoint(
    client_id: str,
    client_update: ClientUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update client
    SECURITY: Verifies user has access to client
    """
    client_data = client_update.model_dump(exclude_unset=True)
    updated = update_client(db, client_id, client_data, current_user)
    if not updated:
        raise HTTPException(status_code=404, detail="Client not found or access denied")
    return updated


@app.delete("/api/clients/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client_endpoint(
    client_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete client (soft delete - admin only)
    SECURITY: Admin only
    """
    success = delete_client(db, client_id, current_user)
    if not success:
        raise HTTPException(status_code=404, detail="Client not found or access denied")


@app.get("/api/clients/active/list", response_model=List[ClientResponse])
def get_active_clients_endpoint(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all active clients
    SECURITY: Returns only clients user has access to
    """
    return get_active_clients(db, current_user, skip, limit)


# ============================================================================
# EMPLOYEE ROUTES (SPRINT 2)
# ============================================================================

@app.post("/api/employees", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
def create_employee_endpoint(
    employee: EmployeeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create new employee
    SECURITY: Supervisor/admin only
    """
    employee_data = employee.model_dump()
    return create_employee(db, employee_data, current_user)


@app.get("/api/employees", response_model=List[EmployeeResponse])
def list_employees(
    skip: int = 0,
    limit: int = 100,
    client_id: Optional[str] = None,
    is_floating_pool: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List employees with filters
    """
    return get_employees(db, current_user, skip, limit, client_id, is_floating_pool)


@app.get("/api/employees/{employee_id}", response_model=EmployeeResponse)
def get_employee_endpoint(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get employee by ID
    """
    employee = get_employee(db, employee_id, current_user)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee


@app.put("/api/employees/{employee_id}", response_model=EmployeeResponse)
def update_employee_endpoint(
    employee_id: int,
    employee_update: EmployeeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update employee
    SECURITY: Supervisor/admin only
    """
    employee_data = employee_update.model_dump(exclude_unset=True)
    updated = update_employee(db, employee_id, employee_data, current_user)
    if not updated:
        raise HTTPException(status_code=404, detail="Employee not found")
    return updated


@app.delete("/api/employees/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_employee_endpoint(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete employee (admin only)
    SECURITY: Admin only
    """
    success = delete_employee(db, employee_id, current_user)
    if not success:
        raise HTTPException(status_code=404, detail="Employee not found")


@app.get("/api/clients/{client_id}/employees", response_model=List[EmployeeResponse])
def get_client_employees(
    client_id: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all employees assigned to a specific client
    SECURITY: Verifies user has access to client
    """
    return get_employees_by_client(db, client_id, current_user, skip, limit)


@app.get("/api/employees/floating-pool/list", response_model=List[EmployeeResponse])
def get_floating_pool_employees_endpoint(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all floating pool employees
    """
    return get_floating_pool_employees(db, current_user, skip, limit)


@app.post("/api/employees/{employee_id}/floating-pool/assign", response_model=EmployeeResponse)
def assign_employee_to_floating_pool(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Assign employee to floating pool
    SECURITY: Supervisor/admin only
    """
    return assign_to_floating_pool(db, employee_id, current_user)


@app.post("/api/employees/{employee_id}/floating-pool/remove", response_model=EmployeeResponse)
def remove_employee_from_floating_pool(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Remove employee from floating pool
    SECURITY: Supervisor/admin only
    """
    return remove_from_floating_pool(db, employee_id, current_user)


@app.post("/api/employees/{employee_id}/assign-client", response_model=EmployeeResponse)
def assign_employee_to_client_endpoint(
    employee_id: int,
    assignment: EmployeeAssignmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Assign employee to a client
    SECURITY: Supervisor/admin only, verifies client access
    """
    return assign_employee_to_client(db, employee_id, assignment.client_id, current_user)


# ============================================================================
# FLOATING POOL ROUTES (SPRINT 2)
# ============================================================================

@app.post("/api/floating-pool", response_model=FloatingPoolResponse, status_code=status.HTTP_201_CREATED)
def create_floating_pool_entry_endpoint(
    pool_entry: FloatingPoolCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create new floating pool entry
    SECURITY: Supervisor/admin only
    """
    pool_data = pool_entry.model_dump()
    return create_floating_pool_entry(db, pool_data, current_user)


@app.get("/api/floating-pool", response_model=List[FloatingPoolResponse])
def list_floating_pool_entries(
    skip: int = 0,
    limit: int = 100,
    employee_id: Optional[int] = None,
    available_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List floating pool entries with filters
    """
    return get_floating_pool_entries(db, current_user, skip, limit, employee_id, available_only)


@app.get("/api/floating-pool/{pool_id}", response_model=FloatingPoolResponse)
def get_floating_pool_entry_endpoint(
    pool_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get floating pool entry by ID
    """
    pool_entry = get_floating_pool_entry(db, pool_id, current_user)
    if not pool_entry:
        raise HTTPException(status_code=404, detail="Floating pool entry not found")
    return pool_entry


@app.put("/api/floating-pool/{pool_id}", response_model=FloatingPoolResponse)
def update_floating_pool_entry_endpoint(
    pool_id: int,
    pool_update: FloatingPoolUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update floating pool entry
    SECURITY: Supervisor/admin only
    """
    pool_data = pool_update.model_dump(exclude_unset=True)
    updated = update_floating_pool_entry(db, pool_id, pool_data, current_user)
    if not updated:
        raise HTTPException(status_code=404, detail="Floating pool entry not found")
    return updated


@app.delete("/api/floating-pool/{pool_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_floating_pool_entry_endpoint(
    pool_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete floating pool entry
    SECURITY: Supervisor/admin only
    """
    success = delete_floating_pool_entry(db, pool_id, current_user)
    if not success:
        raise HTTPException(status_code=404, detail="Floating pool entry not found")


@app.post("/api/floating-pool/assign", response_model=FloatingPoolResponse)
def assign_floating_pool_employee_to_client(
    assignment: FloatingPoolAssignmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Assign floating pool employee to a client
    SECURITY: Supervisor/admin only, verifies client access
    """
    return assign_floating_pool_to_client(
        db,
        assignment.employee_id,
        assignment.client_id,
        assignment.available_from,
        assignment.available_to,
        current_user,
        assignment.notes
    )


@app.post("/api/floating-pool/unassign", response_model=FloatingPoolResponse)
def unassign_floating_pool_employee_from_client(
    unassignment: FloatingPoolUnassignmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Unassign floating pool employee from client
    SECURITY: Supervisor/admin only
    """
    return unassign_floating_pool_from_client(db, unassignment.pool_id, current_user)


@app.get("/api/floating-pool/available/list")
def get_available_floating_pool_list(
    as_of_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all currently available floating pool employees
    """
    return get_available_floating_pool_employees(db, current_user, as_of_date)


@app.get("/api/clients/{client_id}/floating-pool", response_model=List[FloatingPoolResponse])
def get_client_floating_pool_assignments(
    client_id: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all floating pool assignments for a specific client
    SECURITY: Verifies user has access to client
    """
    return get_floating_pool_assignments_by_client(db, client_id, current_user, skip, limit)


# ============================================================================
# INFERENCE ENGINE ROUTES
# ============================================================================

@app.get("/api/inference/cycle-time/{product_id}")
def infer_cycle_time(
    product_id: int,
    shift_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Infer ideal cycle time using 5-level fallback"""
    value, confidence, source, is_estimated = InferenceEngine.infer_ideal_cycle_time(
        db, product_id, shift_id
    )

    confidence_flag = InferenceEngine.flag_low_confidence(confidence)

    return {
        "product_id": product_id,
        "shift_id": shift_id,
        "ideal_cycle_time": value,
        "confidence_score": confidence,
        "source_level": source,
        "is_estimated": is_estimated,
        **confidence_flag
    }


# ============================================================================
# REPORT GENERATION ROUTES (SPRINT 4.2)
# ============================================================================

from backend.reports.pdf_generator import PDFReportGenerator
from backend.reports.excel_generator import ExcelReportGenerator
from backend.services.email_service import EmailService
from pydantic import BaseModel

# Optional scheduler import (may not be available in test environment)
try:
    from backend.tasks.daily_reports import scheduler as report_scheduler
except ImportError:
    report_scheduler = None


class ReportEmailRequest(BaseModel):
    """Request model for sending reports via email"""
    client_id: Optional[int] = None
    start_date: date
    end_date: date
    recipient_emails: List[str]
    include_excel: bool = False


@app.get("/api/reports/pdf")
def generate_pdf_report(
    client_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    kpis: Optional[str] = None,  # Comma-separated KPI keys
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate and download PDF report
    Query params:
    - client_id: Optional client filter
    - start_date: Report start date (default: 30 days ago)
    - end_date: Report end date (default: today)
    - kpis: Comma-separated KPI keys to include (default: all)
    """
    # Default date range
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    # Parse KPIs
    kpis_to_include = None
    if kpis:
        kpis_to_include = [k.strip() for k in kpis.split(',')]

    try:
        # Generate PDF
        pdf_generator = PDFReportGenerator(db)
        pdf_buffer = pdf_generator.generate_report(
            client_id=client_id,
            start_date=start_date,
            end_date=end_date,
            kpis_to_include=kpis_to_include
        )

        # Determine filename
        client_name = "All_Clients"
        if client_id:
            from backend.schemas.client import Client
            client = db.query(Client).filter(Client.client_id == client_id).first()
            if client:
                client_name = client.name.replace(' ', '_')

        filename = f"KPI_Report_{client_name}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf"

        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF report: {str(e)}")


@app.get("/api/reports/excel")
def generate_excel_report(
    client_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate and download Excel report
    Query params:
    - client_id: Optional client filter
    - start_date: Report start date (default: 30 days ago)
    - end_date: Report end date (default: today)
    """
    # Default date range
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    try:
        # Generate Excel
        excel_generator = ExcelReportGenerator(db)
        excel_buffer = excel_generator.generate_report(
            client_id=client_id,
            start_date=start_date,
            end_date=end_date
        )

        # Determine filename
        client_name = "All_Clients"
        if client_id:
            from backend.schemas.client import Client
            client = db.query(Client).filter(Client.client_id == client_id).first()
            if client:
                client_name = client.name.replace(' ', '_')

        filename = f"KPI_Report_{client_name}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.xlsx"

        return StreamingResponse(
            excel_buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate Excel report: {str(e)}")


@app.post("/api/reports/email")
def send_report_via_email(
    request: ReportEmailRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Send KPI report via email
    Body:
    {
        "client_id": 1,  // optional
        "start_date": "2024-01-01",
        "end_date": "2024-01-31",
        "recipient_emails": ["user@example.com"],
        "include_excel": false
    }
    """
    try:
        # Generate PDF
        pdf_generator = PDFReportGenerator(db)
        pdf_buffer = pdf_generator.generate_report(
            client_id=request.client_id,
            start_date=request.start_date,
            end_date=request.end_date
        )

        # Get client name
        client_name = "All Clients"
        if request.client_id:
            from backend.schemas.client import Client
            client = db.query(Client).filter(Client.client_id == request.client_id).first()
            if client:
                client_name = client.name

        # Send email
        email_service = EmailService()
        result = email_service.send_kpi_report(
            to_emails=request.recipient_emails,
            client_name=client_name,
            report_date=datetime.now(),
            pdf_content=pdf_buffer.getvalue()
        )

        if result['success']:
            return {
                "message": "Report sent successfully",
                "recipients": request.recipient_emails,
                "client": client_name
            }
        else:
            raise HTTPException(status_code=500, detail=result.get('message', 'Failed to send email'))

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send report: {str(e)}")


@app.post("/api/reports/schedule/trigger")
def trigger_daily_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Manually trigger daily report generation for all clients
    SECURITY: Admin only
    """
    if current_user.role not in ['admin', 'super_admin']:
        raise HTTPException(status_code=403, detail="Admin access required")

    if report_scheduler is None:
        raise HTTPException(status_code=503, detail="Report scheduler not available")

    try:
        report_scheduler.send_daily_reports()
        return {"message": "Daily reports triggered successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger reports: {str(e)}")


@app.get("/api/reports/test-email")
def test_email_configuration(
    test_email: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Test email configuration by sending a test email
    SECURITY: Admin only
    """
    if current_user.role not in ['admin', 'super_admin']:
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        email_service = EmailService()
        result = email_service.send_test_email(test_email)

        if result['success']:
            return {"message": f"Test email sent successfully to {test_email}"}
        else:
            raise HTTPException(status_code=500, detail=result.get('error', 'Failed to send test email'))

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Email test failed: {str(e)}")


# Start report scheduler on application startup
@app.on_event("startup")
async def startup_event():
    """Initialize application services"""
    # Start daily report scheduler
    if report_scheduler is not None:
        try:
            report_scheduler.start()
        except Exception as e:
            print(f"Warning: Failed to start report scheduler: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup application services"""
    # Stop report scheduler
    if report_scheduler is not None:
        try:
            report_scheduler.stop()
        except Exception as e:
            print(f"Warning: Failed to stop report scheduler: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
