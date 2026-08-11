"""
AUDIT_ENTRY table ORM schema (SQLAlchemy)
Entity-level change trail: who changed what, when, and from what to what.
"""

import enum
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import JSON, DateTime, Enum, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class AuditOperation(str, enum.Enum):
    """The kind of change recorded."""

    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class AuditEntry(Base):
    """AUDIT_ENTRY table - one row per audited entity change."""

    __tablename__ = "AUDIT_ENTRY"
    __table_args__ = (
        Index("ix_audit_entity", "table_name", "record_pk"),
        {"extend_existing": True},
    )

    entry_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    # Actor. NULL user id means system-initiated (scheduler, migration, CLI).
    actor_user_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    # Snapshot, deliberately not a FK: audit history must stay readable after a
    # user is renamed or deactivated, which is exactly when it is needed.
    actor_username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    table_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # Stringified single-column PK; every ORM table was verified to have one.
    record_pk: Mapped[str] = mapped_column(String(64), nullable=False)

    operation: Mapped[AuditOperation] = mapped_column(Enum(AuditOperation), nullable=False)

    #: {field: {"old": ..., "new": ...}}, with REDACTED_FIELDS masked.
    changes: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Captured now though reads are admin-only: adding it later would need a
    # backfill over rows whose tenant can no longer be reconstructed.
    client_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)

    request_method: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    request_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
