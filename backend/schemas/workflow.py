"""
WORKFLOW_TRANSITION_LOG table ORM schema (SQLAlchemy)
Audit trail for work order status transitions
Implements Phase 10: Flexible Workflow Foundation
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.sql import func
from backend.database import Base


class WorkflowTransitionLog(Base):
    """
    WORKFLOW_TRANSITION_LOG table - Audit trail for all status transitions

    Every status change on a work order creates a record here for:
    - Complete audit trail
    - Elapsed time calculations
    - Workflow analytics
    - Compliance and traceability
    """
    __tablename__ = "WORKFLOW_TRANSITION_LOG"
    __table_args__ = (
        # Composite indexes for query performance
        Index('ix_transition_workorder', 'work_order_id'),
        Index('ix_transition_client_date', 'client_id', 'transitioned_at'),
        Index('ix_transition_status', 'to_status', 'transitioned_at'),
        {"extend_existing": True}
    )

    # Primary key
    transition_id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign keys
    work_order_id = Column(
        String(50),
        ForeignKey('WORK_ORDER.work_order_id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    client_id = Column(
        String(50),
        ForeignKey('CLIENT.client_id'),
        nullable=False,
        index=True
    )

    # Transition details
    from_status = Column(String(20), nullable=True)   # NULL for initial creation
    to_status = Column(String(20), nullable=False)
    transitioned_by = Column(Integer, ForeignKey('USER.user_id'), nullable=True)
    transitioned_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)

    # Optional context
    notes = Column(Text)                               # Transition reason/notes
    trigger_source = Column(String(50))                # 'manual', 'automatic', 'bulk', 'api'

    # Elapsed time snapshot (calculated at transition time)
    elapsed_from_received_hours = Column(Integer)      # Hours since received_date
    elapsed_from_previous_hours = Column(Integer)      # Hours since previous transition
