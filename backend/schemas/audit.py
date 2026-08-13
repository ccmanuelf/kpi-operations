"""Audit trail response models."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class AuditEntryResponse(BaseModel):
    """One recorded change."""

    model_config = ConfigDict(from_attributes=True)

    entry_id: int
    occurred_at: datetime
    actor_user_id: Optional[str]
    actor_username: Optional[str]
    table_name: str
    record_pk: str
    operation: str
    changes: Optional[Dict[str, Any]]
    client_id: Optional[str]
    request_method: Optional[str]
    request_path: Optional[str]


class AuditListResponse(BaseModel):
    """A page of entries, plus when the trail itself begins.

    ``trail_started_at`` exists because there is no backfill: an absent change
    from before deployment is correct behaviour, and callers need to be able to
    tell that apart from a bug.
    """

    entries: List[AuditEntryResponse]
    total: int
    trail_started_at: Optional[datetime]
