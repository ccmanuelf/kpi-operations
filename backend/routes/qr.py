"""
QR Code API Routes
Provides QR code generation and lookup endpoints for work orders, products, jobs, and employees
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import Optional
from urllib.parse import unquote

from backend.database import get_db
from backend.auth.jwt import get_current_user
from backend.schemas.user import User
from backend.middleware.client_auth import verify_client_access
from backend.models.qr import QRCodeData, QREntityType, QRGenerateRequest, QRLookupResponse, QRCodeResponse
from backend.services.qr_service import QRService, QRServiceError

# Import ORM schemas for database queries
from backend.schemas.work_order import WorkOrder
from backend.schemas.product import Product
from backend.schemas.job import Job
from backend.schemas.employee import Employee

router = APIRouter(prefix="/api/qr", tags=["qr"])


def _entity_to_dict(entity) -> dict:
    """
    Convert SQLAlchemy ORM object to dictionary

    Handles common column types including Decimal and datetime
    """
    result = {}
    for column in entity.__table__.columns:
        value = getattr(entity, column.name)
        # Convert Decimal to float for JSON serialization
        if hasattr(value, "is_integer"):  # Decimal check
            value = float(value)
        # Convert datetime to ISO string
        if hasattr(value, "isoformat"):
            value = value.isoformat()
        # Convert enum to string
        if hasattr(value, "value"):
            value = value.value
        result[column.name] = value
    return result


@router.get(
    "/lookup",
    response_model=QRLookupResponse,
    summary="Decode QR data and lookup entity",
    description="""
    Decode a QR data string and return the corresponding entity with auto-fill fields.

    **Usage:**
    1. Scan QR code to get JSON string
    2. URL-encode the JSON string
    3. Pass as 'data' query parameter

    **Example:**
    ```
    GET /api/qr/lookup?data=%7B%22type%22%3A%22work_order%22%2C%22id%22%3A%22WO-001%22%2C%22version%22%3A%221.0%22%7D
    ```

    **Security:**
    - Work orders: Enforces client access control
    - Products: Enforces client access control
    - Jobs: Enforces client access control via client_id_fk
    - Employees: Requires authentication

    **Returns:**
    - entity_type: Type of entity found
    - entity_id: ID of the entity
    - entity_data: Full entity data from database
    - auto_fill_fields: Fields to pre-populate in entry forms
    """,
    responses={
        200: {"description": "Entity found and returned with auto-fill fields"},
        400: {"description": "Invalid QR data format"},
        403: {"description": "Access denied to this entity"},
        404: {"description": "Entity not found"},
    },
)
async def qr_lookup(
    data: str = Query(..., description="URL-encoded JSON string from QR code scan"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QRLookupResponse:
    """
    GET /api/qr/lookup - Decode QR data and return entity with auto-fill fields
    """
    # URL-decode and parse the QR data string
    try:
        decoded_data = unquote(data)
        qr_data = QRService.decode_qr_string(decoded_data)
    except QRServiceError as e:
        logger.exception("Failed to decode QR data: %s", e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid QR code data")

    entity_type = qr_data.type
    entity_id = qr_data.id
    entity_data = None
    entity = None

    # Look up entity based on type
    if entity_type == QREntityType.WORK_ORDER or entity_type == "work_order":
        entity = db.query(WorkOrder).filter(WorkOrder.work_order_id == entity_id).first()
        if not entity:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Work order '{entity_id}' not found")
        # Enforce client access control
        verify_client_access(current_user, entity.client_id)
        entity_data = _entity_to_dict(entity)

    elif entity_type == QREntityType.PRODUCT or entity_type == "product":
        # Products can be looked up by product_id (int) or product_code (str)
        entity = (
            db.query(Product).filter((Product.product_id == entity_id) | (Product.product_code == entity_id)).first()
        )
        if not entity:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product '{entity_id}' not found")
        # Enforce client access control (products are now multi-tenant)
        verify_client_access(current_user, entity.client_id)
        entity_data = _entity_to_dict(entity)

    elif entity_type == QREntityType.JOB or entity_type == "job":
        entity = db.query(Job).filter(Job.job_id == entity_id).first()
        if not entity:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job '{entity_id}' not found")
        # Enforce client access control via client_id_fk
        verify_client_access(current_user, entity.client_id_fk)
        entity_data = _entity_to_dict(entity)

    elif entity_type == QREntityType.EMPLOYEE or entity_type == "employee":
        # Employees can be looked up by employee_id (int) or employee_code (str)
        try:
            emp_id = int(entity_id)
            entity = db.query(Employee).filter(Employee.employee_id == emp_id).first()
        except ValueError:
            entity = db.query(Employee).filter(Employee.employee_code == entity_id).first()

        if not entity:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Employee '{entity_id}' not found")
        entity_data = _entity_to_dict(entity)

    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported entity type: {entity_type}")

    # Get auto-fill fields for the entity
    auto_fill_fields = QRService.get_auto_fill_fields(entity_type, entity_data)

    return QRLookupResponse(
        entity_type=entity_type if isinstance(entity_type, str) else entity_type.value,
        entity_id=entity_id,
        entity_data=entity_data,
        auto_fill_fields=auto_fill_fields,
    )


@router.get(
    "/work-order/{work_order_id}/image",
    summary="Get QR code image for work order",
    description="""
    Generate and return a QR code PNG image for a work order.

    **Security:** Enforces client access control - user must have access to the work order's client.

    **Returns:** PNG image (image/png content-type)
    """,
    responses={
        200: {"description": "QR code PNG image", "content": {"image/png": {}}},
        403: {"description": "Access denied to this work order"},
        404: {"description": "Work order not found"},
    },
)
async def get_work_order_qr_image(
    work_order_id: str,
    size: Optional[int] = Query(200, ge=100, le=500, description="QR code image size in pixels"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """
    GET /api/qr/work-order/{work_order_id}/image - Get QR code PNG for work order
    """
    # Look up work order
    work_order = db.query(WorkOrder).filter(WorkOrder.work_order_id == work_order_id).first()
    if not work_order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Work order '{work_order_id}' not found")

    # Enforce client access control
    verify_client_access(current_user, work_order.client_id)

    # Generate QR code
    try:
        qr_data = QRService.create_qr_data(QREntityType.WORK_ORDER.value, work_order_id)
        image_bytes = QRService.generate_qr_image(qr_data, size)

        return Response(
            content=image_bytes,
            media_type="image/png",
            headers={"Content-Disposition": f"inline; filename=qr_work_order_{work_order_id}.png"},
        )
    except QRServiceError as e:
        logger.exception("Failed to generate work order QR image: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to process QR code")


@router.get(
    "/product/{product_id}/image",
    summary="Get QR code image for product",
    description="""
    Generate and return a QR code PNG image for a product.

    The product can be identified by either product_id (integer) or product_code (string).

    **Returns:** PNG image (image/png content-type)
    """,
    responses={
        200: {"description": "QR code PNG image", "content": {"image/png": {}}},
        404: {"description": "Product not found"},
    },
)
async def get_product_qr_image(
    product_id: str,
    size: Optional[int] = Query(200, ge=100, le=500, description="QR code image size in pixels"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """
    GET /api/qr/product/{product_id}/image - Get QR code PNG for product
    """
    # Look up product by ID or code
    product = None
    try:
        prod_id = int(product_id)
        product = db.query(Product).filter(Product.product_id == prod_id).first()
    except ValueError:
        product = db.query(Product).filter(Product.product_code == product_id).first()

    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product '{product_id}' not found")

    # Enforce client access control (products are now multi-tenant)
    verify_client_access(current_user, product.client_id)

    # Use product_code as the identifier in the QR code for consistency
    qr_identifier = product.product_code

    # Generate QR code
    try:
        qr_data = QRService.create_qr_data(QREntityType.PRODUCT.value, qr_identifier)
        image_bytes = QRService.generate_qr_image(qr_data, size)

        return Response(
            content=image_bytes,
            media_type="image/png",
            headers={"Content-Disposition": f"inline; filename=qr_product_{qr_identifier}.png"},
        )
    except QRServiceError as e:
        logger.exception("Failed to generate product QR image: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to process QR code")


@router.get(
    "/job/{job_id}/image",
    summary="Get QR code image for job",
    description="""
    Generate and return a QR code PNG image for a job (work order line item).

    **Security:** Enforces client access control via job's client_id_fk.

    **Returns:** PNG image (image/png content-type)
    """,
    responses={
        200: {"description": "QR code PNG image", "content": {"image/png": {}}},
        403: {"description": "Access denied to this job"},
        404: {"description": "Job not found"},
    },
)
async def get_job_qr_image(
    job_id: str,
    size: Optional[int] = Query(200, ge=100, le=500, description="QR code image size in pixels"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """
    GET /api/qr/job/{job_id}/image - Get QR code PNG for job
    """
    # Look up job
    job = db.query(Job).filter(Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job '{job_id}' not found")

    # Enforce client access control
    verify_client_access(current_user, job.client_id_fk)

    # Generate QR code
    try:
        qr_data = QRService.create_qr_data(QREntityType.JOB.value, job_id)
        image_bytes = QRService.generate_qr_image(qr_data, size)

        return Response(
            content=image_bytes,
            media_type="image/png",
            headers={"Content-Disposition": f"inline; filename=qr_job_{job_id}.png"},
        )
    except QRServiceError as e:
        logger.exception("Failed to generate job QR image: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to process QR code")


@router.get(
    "/employee/{employee_id}/image",
    summary="Get QR code image for employee",
    description="""
    Generate and return a QR code PNG image for an employee.

    The employee can be identified by either employee_id (integer) or employee_code (string).

    **Returns:** PNG image (image/png content-type)
    """,
    responses={
        200: {"description": "QR code PNG image", "content": {"image/png": {}}},
        404: {"description": "Employee not found"},
    },
)
async def get_employee_qr_image(
    employee_id: str,
    size: Optional[int] = Query(200, ge=100, le=500, description="QR code image size in pixels"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """
    GET /api/qr/employee/{employee_id}/image - Get QR code PNG for employee
    """
    # Look up employee by ID or code
    employee = None
    try:
        emp_id = int(employee_id)
        employee = db.query(Employee).filter(Employee.employee_id == emp_id).first()
    except ValueError:
        employee = db.query(Employee).filter(Employee.employee_code == employee_id).first()

    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Employee '{employee_id}' not found")

    # Use employee_code as the identifier in the QR code for consistency
    qr_identifier = employee.employee_code

    # Generate QR code
    try:
        qr_data = QRService.create_qr_data(QREntityType.EMPLOYEE.value, qr_identifier)
        image_bytes = QRService.generate_qr_image(qr_data, size)

        return Response(
            content=image_bytes,
            media_type="image/png",
            headers={"Content-Disposition": f"inline; filename=qr_employee_{qr_identifier}.png"},
        )
    except QRServiceError as e:
        logger.exception("Failed to generate employee QR image: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to process QR code")


@router.post(
    "/generate",
    response_model=QRCodeResponse,
    summary="Generate QR code for any entity",
    description="""
    Generate a QR code for any supported entity type.

    **Supported entity types:**
    - work_order
    - product
    - job
    - employee

    **Security:**
    - work_order: Enforces client access control
    - job: Enforces client access control
    - product/employee: Requires authentication only

    **Returns:** QR code metadata with the encoded data string
    """,
    responses={
        200: {"description": "QR code generated successfully"},
        400: {"description": "Invalid entity type or ID"},
        403: {"description": "Access denied to this entity"},
        404: {"description": "Entity not found"},
    },
)
async def generate_qr_code(
    request: QRGenerateRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> QRCodeResponse:
    """
    POST /api/qr/generate - Generate QR code for any entity type
    """
    entity_type = request.entity_type
    entity_id = request.entity_id

    # Validate entity exists and user has access
    if entity_type == QREntityType.WORK_ORDER or entity_type == "work_order":
        work_order = db.query(WorkOrder).filter(WorkOrder.work_order_id == entity_id).first()
        if not work_order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Work order '{entity_id}' not found")
        verify_client_access(current_user, work_order.client_id)

    elif entity_type == QREntityType.PRODUCT or entity_type == "product":
        product = None
        try:
            prod_id = int(entity_id)
            product = db.query(Product).filter(Product.product_id == prod_id).first()
        except ValueError:
            product = db.query(Product).filter(Product.product_code == entity_id).first()
        if not product:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product '{entity_id}' not found")
        # Enforce client access control (products are now multi-tenant)
        verify_client_access(current_user, product.client_id)

    elif entity_type == QREntityType.JOB or entity_type == "job":
        job = db.query(Job).filter(Job.job_id == entity_id).first()
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job '{entity_id}' not found")
        verify_client_access(current_user, job.client_id_fk)

    elif entity_type == QREntityType.EMPLOYEE or entity_type == "employee":
        employee = None
        try:
            emp_id = int(entity_id)
            employee = db.query(Employee).filter(Employee.employee_id == emp_id).first()
        except ValueError:
            employee = db.query(Employee).filter(Employee.employee_code == entity_id).first()
        if not employee:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Employee '{entity_id}' not found")

    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported entity type: {entity_type}")

    # Generate QR data string
    type_value = entity_type if isinstance(entity_type, str) else entity_type.value
    qr_data_string = QRService.get_qr_data_string(type_value, entity_id)

    return QRCodeResponse(
        entity_type=type_value,
        entity_id=entity_id,
        qr_data_string=qr_data_string,
        message="QR code generated successfully",
    )


@router.post(
    "/generate/image",
    summary="Generate and return QR code image for any entity",
    description="""
    Generate and return a QR code PNG image for any supported entity type.

    This is the same as POST /generate but returns the actual image instead of metadata.

    **Returns:** PNG image (image/png content-type)
    """,
    responses={
        200: {"description": "QR code PNG image", "content": {"image/png": {}}},
        400: {"description": "Invalid entity type or ID"},
        403: {"description": "Access denied to this entity"},
        404: {"description": "Entity not found"},
    },
)
async def generate_qr_code_image(
    request: QRGenerateRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Response:
    """
    POST /api/qr/generate/image - Generate and return QR code PNG for any entity
    """
    entity_type = request.entity_type
    entity_id = request.entity_id
    size = request.size or 200

    # Validate entity exists and user has access (same as /generate)
    if entity_type == QREntityType.WORK_ORDER or entity_type == "work_order":
        work_order = db.query(WorkOrder).filter(WorkOrder.work_order_id == entity_id).first()
        if not work_order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Work order '{entity_id}' not found")
        verify_client_access(current_user, work_order.client_id)

    elif entity_type == QREntityType.PRODUCT or entity_type == "product":
        product = None
        try:
            prod_id = int(entity_id)
            product = db.query(Product).filter(Product.product_id == prod_id).first()
        except ValueError:
            product = db.query(Product).filter(Product.product_code == entity_id).first()
        if not product:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product '{entity_id}' not found")
        # Enforce client access control (products are now multi-tenant)
        verify_client_access(current_user, product.client_id)

    elif entity_type == QREntityType.JOB or entity_type == "job":
        job = db.query(Job).filter(Job.job_id == entity_id).first()
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job '{entity_id}' not found")
        verify_client_access(current_user, job.client_id_fk)

    elif entity_type == QREntityType.EMPLOYEE or entity_type == "employee":
        employee = None
        try:
            emp_id = int(entity_id)
            employee = db.query(Employee).filter(Employee.employee_id == emp_id).first()
        except ValueError:
            employee = db.query(Employee).filter(Employee.employee_code == entity_id).first()
        if not employee:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Employee '{entity_id}' not found")

    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported entity type: {entity_type}")

    # Generate QR code image
    try:
        type_value = entity_type if isinstance(entity_type, str) else entity_type.value
        qr_data = QRService.create_qr_data(type_value, entity_id)
        image_bytes = QRService.generate_qr_image(qr_data, size)

        return Response(
            content=image_bytes,
            media_type="image/png",
            headers={"Content-Disposition": f"inline; filename=qr_{type_value}_{entity_id}.png"},
        )
    except QRServiceError as e:
        logger.exception("Failed to generate QR image: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to process QR code")
