"""
EVENT_STORE Schema
Phase 3: Domain Events Infrastructure

Provides persistent storage for domain events.
Enables event replay, audit trails, and event sourcing.
"""

from sqlalchemy import Column, Integer, String, DateTime, JSON, Index, func, Text
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

from backend.database import Base


class EventStore(Base):
    """
    Persistent storage for domain events.

    Stores all domain events for:
    - Audit trail compliance
    - Event replay/sourcing
    - Analytics and reporting
    - Debugging and troubleshooting
    """

    __tablename__ = "EVENT_STORE"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(36), unique=True, nullable=False, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    aggregate_type = Column(String(50), nullable=False)
    aggregate_id = Column(String(50), nullable=False)
    client_id = Column(String(50), index=True)
    triggered_by = Column(Integer)
    occurred_at = Column(DateTime, nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    # Composite indexes for common queries
    __table_args__ = (
        Index("ix_event_store_aggregate", "aggregate_type", "aggregate_id"),
        Index("ix_event_store_client_time", "client_id", "occurred_at"),
        Index("ix_event_store_type_time", "event_type", "occurred_at"),
    )

    def __repr__(self):
        return f"<EventStore(id={self.id}, event_type={self.event_type}, " f"aggregate_id={self.aggregate_id})>"

    @classmethod
    def from_domain_event(cls, event) -> "EventStore":
        """
        Create EventStore record from a DomainEvent.

        Args:
            event: DomainEvent instance

        Returns:
            EventStore instance ready for persistence
        """
        return cls(
            event_id=event.event_id,
            event_type=event.event_type,
            aggregate_type=event.aggregate_type,
            aggregate_id=event.aggregate_id,
            client_id=event.client_id,
            triggered_by=event.triggered_by,
            occurred_at=event.occurred_at,
            payload=event.to_dict(),
        )


def create_event_persistence_handler(db_session_factory):
    """
    Create a persistence handler for the event bus.

    Args:
        db_session_factory: Callable that returns a database session

    Returns:
        Handler function for persisting events
    """

    def persist_event(event) -> None:
        """Persist a domain event to EVENT_STORE."""
        session = db_session_factory()
        try:
            event_record = EventStore.from_domain_event(event)
            session.add(event_record)
            session.commit()
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()

    return persist_event
