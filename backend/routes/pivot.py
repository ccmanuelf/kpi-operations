"""Pivot summary API (Cycle 4 PR-A, spec §5): pre-defined time buckets and
groupings over the dataset registry; CSV twin per the data-first position."""

import csv
import io
from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.auth.jwt import ClientScope, get_current_user, resolve_client_scope
from backend.database import get_db
from backend.orm.user import User
from backend.pivot.buckets import VALID_BUCKETS
from backend.pivot.engine import run_pivot
from backend.pivot.registry import DATASETS
from backend.utils.date_range import validate_date_range

router = APIRouter(prefix="/api/pivot", tags=["Pivot Summaries"])


def _run(
    db: Session,
    dataset: str,
    bucket: str,
    group_by: Optional[str],
    start_date: date,
    end_date: date,
    scope: ClientScope,
) -> dict[str, Any]:
    if dataset not in DATASETS:
        raise HTTPException(422, detail=f"dataset must be one of {sorted(DATASETS)}")
    if bucket not in VALID_BUCKETS:
        raise HTTPException(422, detail=f"bucket must be one of {list(VALID_BUCKETS)}")
    allowed = sorted(DATASETS[dataset].group_bys)
    if group_by is not None and group_by not in allowed:
        raise HTTPException(422, detail=f"group_by must be one of {allowed}")
    validate_date_range(start_date, end_date)
    return run_pivot(db, dataset, bucket, group_by, start_date, end_date, scope.client_ids)


@router.get("/{dataset}")
def get_pivot(
    dataset: str,
    bucket: str,
    start_date: date,
    end_date: date,
    group_by: Optional[str] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: ClientScope = Depends(resolve_client_scope),
) -> Any:
    return _run(db, dataset, bucket, group_by, start_date, end_date, scope)


@router.get("/{dataset}/csv")
def get_pivot_csv(
    dataset: str,
    bucket: str,
    start_date: date,
    end_date: date,
    group_by: Optional[str] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: ClientScope = Depends(resolve_client_scope),
) -> StreamingResponse:
    result = _run(db, dataset, bucket, group_by, start_date, end_date, scope)
    buf = io.StringIO()
    fieldnames = ["bucket_start", "group_key"] + [
        k for k in (result["rows"][0] if result["rows"] else result["totals"]) if k not in ("bucket_start", "group_key")
    ]
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for row in result["rows"]:
        writer.writerow(row)
    buf.seek(0)
    filename = f"pivot_{dataset}_{bucket}_{start_date}_{end_date}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
