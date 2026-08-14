"""HOLD_STATUS_TRANSITION table ORM schema (SQLAlchemy).

Append-only history of HOLD_ENTRY.hold_status changes. Mirrors
WORKFLOW_TRANSITION_LOG (backend/orm/workflow.py), which answers the same
question for work orders.

Exists so `backend/calculations/wip_aging.py:active_as_of` can ask "what was
this hold's status on date D" instead of judging past dates by current state.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class HoldStatusTransition(Base):
    __tablename__ = "HOLD_STATUS_TRANSITION"
    __table_args__ = (
        Index("ix_hold_transition_hold", "hold_entry_id"),
        Index("ix_hold_transition_client_date", "client_id", "transitioned_at"),
        Index("ix_hold_transition_status", "to_status", "transitioned_at"),
        {"extend_existing": True},
    )

    transition_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    hold_entry_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("HOLD_ENTRY.hold_entry_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id: Mapped[str] = mapped_column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True)

    # NULL only on the row recording hold creation.
    from_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    to_status: Mapped[str] = mapped_column(String(30), nullable=False)

    transitioned_by: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("USER.user_id"), nullable=True)
    # No server_default: callers always pass an explicit instant, so seeded
    # history can be back-dated and every row's time is caller-controlled.
    transitioned_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    notes: Mapped[Optional[str]] = mapped_column(Text)
