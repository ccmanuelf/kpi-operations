"""
QR Code Pydantic models for request/response validation
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from enum import Enum


class QREntityType(str, Enum):
    """Supported entity types for QR codes"""
    WORK_ORDER = "work_order"
    PRODUCT = "product"
    JOB = "job"
    EMPLOYEE = "employee"


class QRCodeData(BaseModel):
    """
    QR Code data structure - embedded in QR code as JSON

    This is the data encoded in the QR code itself.
    When scanned, this JSON string is decoded to identify the entity.
    """
    type: QREntityType = Field(..., description="Entity type (work_order, product, job, employee)")
    id: str = Field(..., description="Entity identifier")
    version: str = Field(default="1.0", description="QR code schema version for future compatibility")

    class Config:
        use_enum_values = True


class QRGenerateRequest(BaseModel):
    """
    Request model for generating a QR code

    Used when manually generating QR codes via POST /api/qr/generate
    """
    entity_type: QREntityType = Field(..., description="Type of entity to encode")
    entity_id: str = Field(..., description="ID of the entity to encode")
    size: Optional[int] = Field(default=200, ge=100, le=500, description="QR code image size in pixels")

    class Config:
        use_enum_values = True


class QRLookupResponse(BaseModel):
    """
    Response model for QR code lookup

    Contains the full entity data and pre-populated form fields
    """
    entity_type: str = Field(..., description="Type of entity found")
    entity_id: str = Field(..., description="ID of the entity")
    entity_data: Dict[str, Any] = Field(..., description="Full entity data from database")
    auto_fill_fields: Dict[str, Any] = Field(
        ...,
        description="Fields to auto-populate in entry forms based on entity type"
    )

    class Config:
        from_attributes = True


class QRCodeResponse(BaseModel):
    """
    Response model for QR code generation status

    Used for endpoints that return metadata about the generated QR code
    """
    entity_type: str
    entity_id: str
    qr_data_string: str = Field(..., description="JSON string encoded in the QR code")
    message: str = Field(default="QR code generated successfully")
