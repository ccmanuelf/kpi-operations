"""
Pydantic models for Client-specific Defect Type Catalog
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class DefectTypeCatalogBase(BaseModel):
    """Base fields for defect type catalog"""

    defect_code: str = Field(..., min_length=1, max_length=20, description="Short code like SOLDER_DEF")
    defect_name: str = Field(..., min_length=1, max_length=100, description="Display name like Solder Defect")
    description: Optional[str] = Field(None, description="Detailed description for training/reference")
    category: Optional[str] = Field(None, max_length=50, description="Group: Assembly, Material, Process, etc.")
    severity_default: str = Field("MAJOR", description="Default severity: CRITICAL, MAJOR, MINOR")
    industry_standard_code: Optional[str] = Field(None, max_length=50, description="Maps to industry standards")
    sort_order: int = Field(0, ge=0, description="Display order in UI")


class DefectTypeCatalogCreate(DefectTypeCatalogBase):
    """Schema for creating a new defect type"""

    client_id: str = Field(..., min_length=1, max_length=50, description="Client this defect type belongs to")

    class Config:
        json_schema_extra = {
            "example": {
                "client_id": "ELEC-ASSY",
                "defect_code": "SOLDER_DEF",
                "defect_name": "Solder Defect",
                "description": "Issues with solder joints including cold solder, bridges, or insufficient solder",
                "category": "Assembly",
                "severity_default": "MAJOR",
                "industry_standard_code": "IPC-A-610-5.2",
                "sort_order": 1,
            }
        }


class DefectTypeCatalogUpdate(BaseModel):
    """Schema for updating a defect type"""

    defect_code: Optional[str] = Field(None, min_length=1, max_length=20)
    defect_name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    category: Optional[str] = Field(None, max_length=50)
    severity_default: Optional[str] = None
    industry_standard_code: Optional[str] = Field(None, max_length=50)
    is_active: Optional[bool] = None
    sort_order: Optional[int] = Field(None, ge=0)


class DefectTypeCatalogResponse(DefectTypeCatalogBase):
    """Response schema for defect type"""

    defect_type_id: str
    client_id: str
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DefectTypeCatalogBulkCreate(BaseModel):
    """Schema for bulk creating defect types from CSV"""

    client_id: str = Field(..., description="Client to create defect types for")
    defect_types: List[DefectTypeCatalogBase] = Field(..., description="List of defect types to create")


class DefectTypeCatalogCSVRow(BaseModel):
    """Schema for CSV import row"""

    defect_code: str
    defect_name: str
    description: Optional[str] = None
    category: Optional[str] = None
    severity_default: str = "MAJOR"
    industry_standard_code: Optional[str] = None
    sort_order: int = 0

    @classmethod
    def from_csv_dict(cls, row: dict) -> "DefectTypeCatalogCSVRow":
        """Create from CSV row dictionary with flexible column names"""
        return cls(
            defect_code=row.get("defect_code") or row.get("code") or row.get("Defect Code", ""),
            defect_name=row.get("defect_name") or row.get("name") or row.get("Defect Name", ""),
            description=row.get("description") or row.get("Description"),
            category=row.get("category") or row.get("Category"),
            severity_default=row.get("severity_default") or row.get("severity") or row.get("Severity", "MAJOR"),
            industry_standard_code=row.get("industry_standard_code") or row.get("standard_code"),
            sort_order=int(row.get("sort_order") or row.get("order") or 0),
        )
