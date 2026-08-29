"""Response contract for the one genuine JSON route Task 10 found in
`/api/reports` + `/api/export` -- see
docs/superpowers/plans/2026-08-25-response-model-refactor.md's "Task 10 --
CORRECTED" section. Every other route in that area returns a file
(`StreamingResponse`); this is the sole exception.

GET /api/reports/available (routes/reports/comprehensive_reports.py::
get_available_reports) returns a single hardcoded literal dict with no
branches at all -- no `if`, no loop, nothing computed from a request
parameter or a database row. Every key below is present on every call, so
`response_model_exclude_unset` is not needed: there is no branch to omit a
key on. Golden evidence, 10 keys.
"""

from typing import List

from pydantic import BaseModel


class ReportEndpoints(BaseModel):
    pdf: str
    excel: str


class ReportCatalogEntry(BaseModel):
    type: str
    name: str
    description: str
    formats: List[str]
    endpoints: ReportEndpoints


class ReportQueryParameters(BaseModel):
    client_id: str
    start_date: str
    end_date: str


class AvailableReportsResponse(BaseModel):
    """GET /api/reports/available -- golden evidence, 10 keys."""

    reports: List[ReportCatalogEntry]
    query_parameters: ReportQueryParameters
    features: List[str]
