"""
API Routes for Client-specific Defect Type Catalog
Allows clients to manage their own defect types
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
import csv
import io

from backend.database import get_db
from backend.models.defect_type_catalog import (
    DefectTypeCatalogCreate,
    DefectTypeCatalogUpdate,
    DefectTypeCatalogResponse,
    DefectTypeCatalogCSVRow,
)
from backend.crud.defect_type_catalog import (
    create_defect_type,
    get_defect_type,
    get_defect_types_by_client,
    get_global_defect_types,
    update_defect_type,
    delete_defect_type,
    bulk_create_defect_types,
    GLOBAL_CLIENT_ID,
    is_global_client,
)
from backend.auth.jwt import get_current_user, get_current_active_supervisor
from backend.schemas.user import User
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)

router = APIRouter(prefix="/api/defect-types", tags=["Defect Type Catalog"])


@router.get("/constants")
def get_constants():
    """
    Get constants used for defect type management
    """
    return {"GLOBAL_CLIENT_ID": GLOBAL_CLIENT_ID}


@router.post("", response_model=DefectTypeCatalogResponse, status_code=status.HTTP_201_CREATED)
def create_defect_type_endpoint(
    defect_type: DefectTypeCatalogCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor),
):
    """
    Create a new defect type for a client
    Requires supervisor or admin role
    """
    try:
        return create_defect_type(db, defect_type, current_user)
    except ValueError as e:
        logger.exception("Failed to process defect type catalog: %s", e)
        raise HTTPException(status_code=400, detail="Failed to process defect type catalog")


@router.get("/global", response_model=List[DefectTypeCatalogResponse])
def get_global_defect_types_endpoint(
    include_inactive: bool = False, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Get all global defect types (available to all clients)
    """
    return get_global_defect_types(db, include_inactive)


@router.get("/client/{client_id}", response_model=List[DefectTypeCatalogResponse])
def get_client_defect_types(
    client_id: str,
    include_inactive: bool = False,
    include_global: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all defect types for a specific client

    Args:
        client_id: The client ID (use 'GLOBAL' for global types only)
        include_inactive: Include inactive defect types
        include_global: Include global defect types in addition to client-specific (default True)

    Returns:
        List of defect types for the client + global types if requested
    """
    return get_defect_types_by_client(db, client_id, current_user, include_inactive, include_global)


@router.get("/{defect_type_id}", response_model=DefectTypeCatalogResponse)
def get_defect_type_endpoint(
    defect_type_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Get a specific defect type by ID"""
    defect_type = get_defect_type(db, defect_type_id, current_user)
    if not defect_type:
        raise HTTPException(status_code=404, detail="Defect type not found")
    return defect_type


@router.put("/{defect_type_id}", response_model=DefectTypeCatalogResponse)
def update_defect_type_endpoint(
    defect_type_id: str,
    defect_type_update: DefectTypeCatalogUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor),
):
    """
    Update a defect type
    Requires supervisor or admin role
    """
    result = update_defect_type(db, defect_type_id, defect_type_update, current_user)
    if not result:
        raise HTTPException(status_code=404, detail="Defect type not found")
    return result


@router.delete("/{defect_type_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_defect_type_endpoint(
    defect_type_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_supervisor)
):
    """
    Soft delete a defect type (deactivate)
    Requires supervisor or admin role
    """
    if not delete_defect_type(db, defect_type_id, current_user):
        raise HTTPException(status_code=404, detail="Defect type not found")


@router.post("/upload/{client_id}")
async def upload_defect_types_csv(
    client_id: str,
    file: UploadFile = File(...),
    replace_existing: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor),
):
    """
    Upload defect types from CSV file

    CSV format:
    defect_code,defect_name,description,category,severity_default,industry_standard_code,sort_order

    Example:
    SOLDER_DEF,Solder Defect,Issues with solder joints,Assembly,MAJOR,IPC-5.2,1
    COMP_MISS,Component Missing,Missing component on PCB,Assembly,CRITICAL,,2
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    try:
        contents = await file.read()
        decoded = contents.decode("utf-8")
        reader = csv.DictReader(io.StringIO(decoded))

        defect_types = []
        for row in reader:
            try:
                dt = DefectTypeCatalogCSVRow.from_csv_dict(row)
                if dt.defect_code and dt.defect_name:  # Skip empty rows
                    defect_types.append(dt)
            except Exception as e:
                continue  # Skip invalid rows, they'll be counted in errors

        if not defect_types:
            raise HTTPException(status_code=400, detail="No valid defect types found in CSV")

        result = bulk_create_defect_types(db, client_id, defect_types, current_user, replace_existing)

        return {"message": "Upload completed", "client_id": client_id, **result}

    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid file encoding. Use UTF-8")
    except Exception as e:
        logger.exception("Failed to process defect type catalog: %s", e)
        raise HTTPException(status_code=500, detail="Failed to process defect type catalog")


@router.get("/template/download")
def download_csv_template():
    """
    Get CSV template for defect type upload
    Returns the expected format and example data
    """
    return {
        "template": {
            "columns": [
                "defect_code",
                "defect_name",
                "description",
                "category",
                "severity_default",
                "industry_standard_code",
                "sort_order",
            ],
            "example_rows": [
                {
                    "defect_code": "SOLDER_DEF",
                    "defect_name": "Solder Defect",
                    "description": "Issues with solder joints including cold solder, bridges, or insufficient solder",
                    "category": "Assembly",
                    "severity_default": "MAJOR",
                    "industry_standard_code": "IPC-A-610-5.2",
                    "sort_order": 1,
                },
                {
                    "defect_code": "COMP_MISS",
                    "defect_name": "Component Missing",
                    "description": "Required component not present on the PCB",
                    "category": "Assembly",
                    "severity_default": "CRITICAL",
                    "industry_standard_code": "",
                    "sort_order": 2,
                },
            ],
        },
        "notes": [
            "defect_code: Required. Unique short code (max 20 chars)",
            "defect_name: Required. Display name (max 100 chars)",
            "description: Optional. Detailed description for reference",
            "category: Optional. Grouping category (Assembly, Material, Process, etc.)",
            "severity_default: Optional. Default severity (CRITICAL, MAJOR, MINOR). Defaults to MAJOR",
            "industry_standard_code: Optional. Reference to industry standards",
            "sort_order: Optional. Display order (0-999). Defaults to 0",
        ],
    }
