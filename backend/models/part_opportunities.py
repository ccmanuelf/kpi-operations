"""
Pydantic models for PART_OPPORTUNITIES API requests/responses
Used for DPMO (Defects Per Million Opportunities) calculations
"""
from pydantic import BaseModel, Field
from typing import Optional, List


class PartOpportunityBase(BaseModel):
    """Base part opportunity fields"""
    client_id_fk: str = Field(..., description="Client ID for multi-tenant isolation")
    opportunities_per_unit: int = Field(..., gt=0, description="Number of opportunities per unit for DPMO calculation")
    part_description: Optional[str] = Field(None, description="Part description")
    part_category: Optional[str] = Field(None, description="Part category for grouping")
    notes: Optional[str] = Field(None, description="Additional notes")


class PartOpportunityCreate(PartOpportunityBase):
    """Create new part opportunity"""
    part_number: str = Field(..., min_length=1, max_length=100, description="Unique part number (primary key)")


class PartOpportunityUpdate(BaseModel):
    """Update existing part opportunity (all fields optional except part_number)"""
    opportunities_per_unit: Optional[int] = Field(None, gt=0, description="Number of opportunities per unit")
    part_description: Optional[str] = None
    part_category: Optional[str] = None
    notes: Optional[str] = None


class PartOpportunityResponse(PartOpportunityBase):
    """Part opportunity response with all fields"""
    part_number: str

    class Config:
        from_attributes = True


class BulkImportRequest(BaseModel):
    """Bulk import request for CSV uploads"""
    opportunities: List[PartOpportunityCreate] = Field(..., description="List of part opportunities to import")


class BulkImportResponse(BaseModel):
    """Bulk import response with success/failure counts"""
    success_count: int = Field(..., description="Number of successfully imported records")
    failure_count: int = Field(..., description="Number of failed imports")
    errors: List[str] = Field(default_factory=list, description="List of error messages (first 10)")
    total_processed: int = Field(..., description="Total records processed")

    class Config:
        from_attributes = True
