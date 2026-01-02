"""
Manufacturing KPI Platform - FastAPI Backend
Main application with all routes
"""
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, datetime, timedelta
import io
import csv
from decimal import Decimal

from backend.config import settings
from backend.database import get_db, engine, Base
from backend.models.user import UserCreate, UserLogin, UserResponse, Token
from backend.models.production import (
    ProductionEntryCreate,
    ProductionEntryUpdate,
    ProductionEntryResponse,
    ProductionEntryWithKPIs,
    CSVUploadResponse,
    KPICalculationResponse
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
from backend.schemas.user import User
from backend.schemas.product import Product
from backend.schemas.shift import Shift
from backend.auth.jwt import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_user,
    get_current_active_supervisor
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
from backend.reports.pdf_generator import generate_daily_report

# Create tables
Base.metadata.create_all(bind=engine)

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
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    """Register new user"""
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

    # Create user
    hashed_password = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        email=user.email,
        password_hash=hashed_password,
        full_name=user.full_name,
        role=user.role
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return db_user


@app.post("/api/auth/login", response_model=Token)
def login(user_credentials: UserLogin, db: Session = Depends(get_db)):
    """User login"""
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

    # Create access token
    access_token = create_access_token(data={"sub": user.username})

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.from_orm(user)
    )


@app.get("/api/auth/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return current_user


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
        shift_id=shift_id
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get KPI dashboard data"""
    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()

    return get_daily_summary(db, start_date, end_date, current_user)


# ============================================================================
# CSV UPLOAD ROUTE
# ============================================================================

@app.post("/api/production/upload/csv", response_model=CSVUploadResponse)
async def upload_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload production entries via CSV"""
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
            # Parse CSV row
            entry = ProductionEntryCreate(
                product_id=int(row['product_id']),
                shift_id=int(row['shift_id']),
                production_date=datetime.strptime(row['production_date'], '%Y-%m-%d').date(),
                work_order_number=row.get('work_order_number') or None,
                units_produced=int(row['units_produced']),
                run_time_hours=Decimal(row['run_time_hours']),
                employees_assigned=int(row['employees_assigned']),
                defect_count=int(row.get('defect_count', 0)),
                scrap_count=int(row.get('scrap_count', 0)),
                notes=row.get('notes')
            )

            # Create entry
            created = create_production_entry(db, entry, current_user)
            created_entries.append(created.entry_id)
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
    pdf_bytes = generate_daily_report(db, report_date)

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=daily_report_{report_date}.pdf"
        }
    )


# ============================================================================
# REFERENCE DATA ROUTES
# ============================================================================

@app.get("/api/products", response_model=List[dict])
def list_products(db: Session = Depends(get_db)):
    """List all active products"""
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
def list_shifts(db: Session = Depends(get_db)):
    """List all active shifts"""
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
    product_id: Optional[int] = None,
    shift_id: Optional[int] = None,
    downtime_category: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List downtime events with filters"""
    return get_downtime_events(
        db, current_user=current_user, skip=skip, limit=limit, start_date=start_date,
        end_date=end_date, product_id=product_id, shift_id=shift_id,
        downtime_category=downtime_category
    )


@app.get("/api/downtime/{downtime_id}", response_model=DowntimeEventResponse)
def get_downtime(
    downtime_id: int,
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
    downtime_id: int,
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
    downtime_id: int,
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
    product_id: Optional[int] = None,
    shift_id: Optional[int] = None,
    released: Optional[bool] = None,
    hold_category: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List WIP holds with filters"""
    return get_wip_holds(
        db, current_user=current_user, skip=skip, limit=limit, start_date=start_date,
        end_date=end_date, product_id=product_id, shift_id=shift_id,
        released=released, hold_category=hold_category
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Calculate WIP aging analysis"""
    aging_data = calculate_wip_aging(db, product_id, as_of_date or date.today())

    return WIPAgingResponse(
        total_held_quantity=aging_data["total_held_quantity"],
        average_aging_days=aging_data["average_aging_days"],
        aging_0_7_days=aging_data["aging_0_7_days"],
        aging_8_14_days=aging_data["aging_8_14_days"],
        aging_15_30_days=aging_data["aging_15_30_days"],
        aging_over_30_days=aging_data["aging_over_30_days"],
        total_hold_events=aging_data["total_hold_events"],
        calculation_timestamp=datetime.utcnow()
    )


@app.get("/api/kpi/chronic-holds")
def get_chronic_holds(
    threshold_days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Identify chronic WIP holds"""
    return identify_chronic_holds(db, threshold_days)


# ============================================================================
# PHASE 3: ATTENDANCE TRACKING ROUTES
# ============================================================================

@app.post("/api/attendance", response_model=AttendanceRecordResponse, status_code=status.HTTP_201_CREATED)
def create_attendance(
    attendance: AttendanceRecordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create attendance record"""
    return create_attendance_record(db, attendance, current_user)


@app.get("/api/attendance", response_model=List[AttendanceRecordResponse])
def list_attendance(
    skip: int = 0,
    limit: int = 100,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    employee_id: Optional[int] = None,
    shift_id: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List attendance records with filters"""
    return get_attendance_records(
        db, current_user=current_user, skip=skip, limit=limit, start_date=start_date,
        end_date=end_date, employee_id=employee_id,
        shift_id=shift_id, status=status
    )


@app.get("/api/attendance/{attendance_id}", response_model=AttendanceRecordResponse)
def get_attendance(
    attendance_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get attendance record by ID"""
    record = get_attendance_record(db, attendance_id, current_user)
    if not record:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    return record


@app.put("/api/attendance/{attendance_id}", response_model=AttendanceRecordResponse)
def update_attendance(
    attendance_id: int,
    attendance_update: AttendanceRecordUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update attendance record"""
    updated = update_attendance_record(db, attendance_id, attendance_update, current_user)
    if not updated:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    return updated


@app.delete("/api/attendance/{attendance_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attendance(
    attendance_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor)
):
    """Delete attendance record (supervisor only)"""
    success = delete_attendance_record(db, attendance_id, current_user)
    if not success:
        raise HTTPException(status_code=404, detail="Attendance record not found")


@app.get("/api/kpi/absenteeism", response_model=AbsenteeismCalculationResponse)
def calculate_absenteeism_kpi(
    shift_id: int,
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Calculate absenteeism KPI"""
    rate, scheduled, absent, emp_count, absence_count = calculate_absenteeism(
        db, shift_id, start_date, end_date
    )

    return AbsenteeismCalculationResponse(
        shift_id=shift_id,
        start_date=start_date,
        end_date=end_date,
        total_scheduled_hours=scheduled,
        total_hours_worked=scheduled - absent,
        total_hours_absent=absent,
        absenteeism_rate=rate,
        total_employees=emp_count,
        total_absences=absence_count,
        calculation_timestamp=datetime.utcnow()
    )


@app.get("/api/kpi/bradford-factor/{employee_id}")
def get_bradford_factor(
    employee_id: int,
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Calculate Bradford Factor for employee"""
    score = calculate_bradford_factor(db, employee_id, start_date, end_date)

    interpretation = "Low risk"
    if score > 250:
        interpretation = "Critical - Final warning/termination"
    elif score > 125:
        interpretation = "High risk - Formal action required"
    elif score > 50:
        interpretation = "Medium risk - Monitor closely"

    return {
        "employee_id": employee_id,
        "bradford_score": score,
        "interpretation": interpretation,
        "start_date": start_date,
        "end_date": end_date
    }


# ============================================================================
# PHASE 3: SHIFT COVERAGE ROUTES
# ============================================================================

@app.post("/api/coverage", response_model=ShiftCoverageResponse, status_code=status.HTTP_201_CREATED)
def create_coverage(
    coverage: ShiftCoverageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create shift coverage record"""
    return create_shift_coverage(db, coverage, current_user)


@app.get("/api/coverage", response_model=List[ShiftCoverageResponse])
def list_coverage(
    skip: int = 0,
    limit: int = 100,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    shift_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List shift coverage records"""
    return get_shift_coverages(
        db, current_user=current_user, skip=skip, limit=limit,
        start_date=start_date, end_date=end_date, shift_id=shift_id
    )


@app.get("/api/coverage/{coverage_id}", response_model=ShiftCoverageResponse)
def get_coverage(
    coverage_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get shift coverage by ID"""
    coverage = get_shift_coverage(db, coverage_id, current_user)
    if not coverage:
        raise HTTPException(status_code=404, detail="Shift coverage not found")
    return coverage


@app.put("/api/coverage/{coverage_id}", response_model=ShiftCoverageResponse)
def update_coverage(
    coverage_id: int,
    coverage_update: ShiftCoverageUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update shift coverage record"""
    updated = update_shift_coverage(db, coverage_id, coverage_update, current_user)
    if not updated:
        raise HTTPException(status_code=404, detail="Shift coverage not found")
    return updated


@app.delete("/api/coverage/{coverage_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_coverage(
    coverage_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor)
):
    """Delete shift coverage (supervisor only)"""
    success = delete_shift_coverage(db, coverage_id, current_user)
    if not success:
        raise HTTPException(status_code=404, detail="Shift coverage not found")


@app.get("/api/kpi/otd")
def calculate_otd_kpi(
    start_date: date,
    end_date: date,
    product_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Calculate On-Time Delivery KPI"""
    otd_pct, on_time, total = calculate_otd(db, start_date, end_date, product_id)

    return {
        "start_date": start_date,
        "end_date": end_date,
        "product_id": product_id,
        "otd_percentage": otd_pct,
        "on_time_count": on_time,
        "total_orders": total,
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


# ============================================================================
# PHASE 4: QUALITY INSPECTION ROUTES
# ============================================================================

@app.post("/api/quality", response_model=QualityInspectionResponse, status_code=status.HTTP_201_CREATED)
def create_quality(
    inspection: QualityInspectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create quality inspection record"""
    return create_quality_inspection(db, inspection, current_user)


@app.get("/api/quality", response_model=List[QualityInspectionResponse])
def list_quality(
    skip: int = 0,
    limit: int = 100,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    product_id: Optional[int] = None,
    shift_id: Optional[int] = None,
    inspection_stage: Optional[str] = None,
    defect_category: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List quality inspections with filters"""
    return get_quality_inspections(
        db, current_user=current_user, skip=skip, limit=limit, start_date=start_date,
        end_date=end_date, product_id=product_id, shift_id=shift_id,
        inspection_stage=inspection_stage, defect_category=defect_category
    )


@app.get("/api/quality/{inspection_id}", response_model=QualityInspectionResponse)
def get_quality(
    inspection_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get quality inspection by ID"""
    inspection = get_quality_inspection(db, inspection_id, current_user)
    if not inspection:
        raise HTTPException(status_code=404, detail="Quality inspection not found")
    return inspection


@app.put("/api/quality/{inspection_id}", response_model=QualityInspectionResponse)
def update_quality(
    inspection_id: int,
    inspection_update: QualityInspectionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update quality inspection"""
    updated = update_quality_inspection(db, inspection_id, inspection_update, current_user)
    if not updated:
        raise HTTPException(status_code=404, detail="Quality inspection not found")
    return updated


@app.delete("/api/quality/{inspection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_quality(
    inspection_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor)
):
    """Delete quality inspection (supervisor only)"""
    success = delete_quality_inspection(db, inspection_id, current_user)
    if not success:
        raise HTTPException(status_code=404, detail="Quality inspection not found")


@app.get("/api/kpi/ppm", response_model=PPMCalculationResponse)
def calculate_ppm_kpi(
    product_id: int,
    shift_id: int,
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Calculate PPM (Parts Per Million)"""
    ppm, inspected, defects = calculate_ppm(
        db, product_id, shift_id, start_date, end_date
    )

    return PPMCalculationResponse(
        product_id=product_id,
        shift_id=shift_id,
        start_date=start_date,
        end_date=end_date,
        total_units_inspected=inspected,
        total_defects=defects,
        ppm=ppm,
        calculation_timestamp=datetime.utcnow()
    )


@app.get("/api/kpi/dpmo", response_model=DPMOCalculationResponse)
def calculate_dpmo_kpi(
    product_id: int,
    shift_id: int,
    start_date: date,
    end_date: date,
    opportunities_per_unit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Calculate DPMO and Sigma Level"""
    dpmo, sigma, units, defects = calculate_dpmo(
        db, product_id, shift_id, start_date, end_date, opportunities_per_unit
    )

    return DPMOCalculationResponse(
        product_id=product_id,
        shift_id=shift_id,
        start_date=start_date,
        end_date=end_date,
        total_units=units,
        opportunities_per_unit=opportunities_per_unit,
        total_defects=defects,
        dpmo=dpmo,
        sigma_level=sigma,
        calculation_timestamp=datetime.utcnow()
    )


@app.get("/api/kpi/fpy-rty", response_model=FPYRTYCalculationResponse)
def calculate_fpy_rty_kpi(
    product_id: int,
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Calculate FPY and RTY"""
    fpy, good, total = calculate_fpy(db, product_id, start_date, end_date)
    rty, steps = calculate_rty(db, product_id, start_date, end_date)

    return FPYRTYCalculationResponse(
        product_id=product_id,
        start_date=start_date,
        end_date=end_date,
        total_units=total,
        first_pass_good=good,
        fpy_percentage=fpy,
        rty_percentage=rty,
        total_process_steps=len(steps),
        calculation_timestamp=datetime.utcnow()
    )


@app.get("/api/kpi/quality-score")
def get_quality_score(
    product_id: int,
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Calculate comprehensive quality score"""
    return calculate_quality_score(db, product_id, start_date, end_date)


@app.get("/api/kpi/top-defects")
def get_top_defects(
    product_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get top defect types (Pareto analysis)"""
    return identify_top_defects(db, product_id, start_date, end_date, limit)


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
