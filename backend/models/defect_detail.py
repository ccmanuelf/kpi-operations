"""
Pydantic models for DEFECT_DETAIL API requests and responses
Used for API validation, serialization, and documentation
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from backend.schemas.defect_detail import DefectType


class DefectDetailBase(BaseModel):
    """Base defect detail fields shared across schemas"""
    quality_entry_id: str = Field(..., description="Foreign key to QUALITY_ENTRY")
    client_id_fk: str = Field(..., description="Foreign key to CLIENT (multi-tenant)")
    defect_type: DefectType = Field(..., description="Defect category (Stitching, Fabric Defect, etc.)")
    defect_category: Optional[str] = Field(None, max_length=100, description="Defect sub-category")
    defect_count: int = Field(..., ge=0, description="Number of defects found")
    severity: Optional[str] = Field(None, max_length=20, description="Severity level (CRITICAL, MAJOR, MINOR)")
    location: Optional[str] = Field(None, max_length=255, description="Location on product")
    description: Optional[str] = Field(None, description="Detailed defect description")


class DefectDetailCreate(DefectDetailBase):
    """Schema for creating a new defect detail record"""
    defect_detail_id: str = Field(..., max_length=50, description="Unique defect detail identifier")

    class Config:
        json_schema_extra = {
            "example": {
                "defect_detail_id": "DEF-2024-001",
                "quality_entry_id": "QE-2024-001",
                "client_id_fk": "CLIENT-001",
                "defect_type": "Stitching",
                "defect_category": "Loose Thread",
                "defect_count": 5,
                "severity": "MINOR",
                "location": "Left Sleeve",
                "description": "Found loose threads on seam"
            }
        }


class DefectDetailUpdate(BaseModel):
    """Schema for updating defect detail (all fields optional)"""
    quality_entry_id: Optional[str] = None
    client_id_fk: Optional[str] = None
    defect_type: Optional[DefectType] = None
    defect_category: Optional[str] = Field(None, max_length=100)
    defect_count: Optional[int] = Field(None, ge=0)
    severity: Optional[str] = Field(None, max_length=20)
    location: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "defect_count": 3,
                "severity": "MAJOR",
                "description": "Updated count after re-inspection"
            }
        }


class DefectDetailResponse(DefectDetailBase):
    """Schema for defect detail API responses (includes timestamps)"""
    defect_detail_id: str
    created_at: datetime

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "defect_detail_id": "DEF-2024-001",
                "quality_entry_id": "QE-2024-001",
                "client_id_fk": "CLIENT-001",
                "defect_type": "Stitching",
                "defect_category": "Loose Thread",
                "defect_count": 5,
                "severity": "MINOR",
                "location": "Left Sleeve",
                "description": "Found loose threads on seam",
                "created_at": "2024-01-15T10:30:00"
            }
        }


class DefectSummaryResponse(BaseModel):
    """Schema for defect summary by type"""
    defect_type: DefectType = Field(..., description="Defect category")
    total_count: int = Field(..., ge=0, description="Number of defect records")
    defect_count: int = Field(..., ge=0, description="Total defects found")

    class Config:
        json_schema_extra = {
            "example": {
                "defect_type": "Stitching",
                "total_count": 45,
                "defect_count": 120
            }
        }
