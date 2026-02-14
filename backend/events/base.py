"""
Domain Event Base Classes
Phase 3: Domain Events Infrastructure

Provides immutable event base class for all domain events.
Events are value objects that capture significant state changes.
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import uuid4


class DomainEvent(BaseModel):
    """
    Base class for all domain events.

    Events are immutable value objects that capture significant state changes.
    They contain:
    - Unique event ID for deduplication
    - Event type for routing
    - Aggregate information for event sourcing
    - Timestamp for ordering
    - Optional context (client, user)
    """

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: str = ""
    occurred_at: datetime = Field(default_factory=datetime.utcnow)
    aggregate_id: str
    aggregate_type: str
    client_id: Optional[str] = None
    triggered_by: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        frozen = True  # Events are immutable

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for persistence."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "occurred_at": self.occurred_at.isoformat(),
            "aggregate_id": self.aggregate_id,
            "aggregate_type": self.aggregate_type,
            "client_id": self.client_id,
            "triggered_by": self.triggered_by,
            "metadata": self.metadata,
        }


class EventHandler:
    """
    Base class for event handlers.

    Handlers process events and perform side effects like:
    - Updating read models
    - Sending notifications
    - Triggering workflows
    """

    def __init__(self, is_async: bool = False, priority: int = 100):
        """
        Initialize handler.

        Args:
            is_async: If True, handler runs after HTTP response
            priority: Lower numbers run first (default 100)
        """
        self.is_async = is_async
        self.priority = priority

    async def handle(self, event: DomainEvent) -> None:
        """
        Handle the event.

        Override this method in subclasses.

        Args:
            event: The domain event to handle
        """
        raise NotImplementedError("Subclasses must implement handle()")

    def can_handle(self, event: DomainEvent) -> bool:
        """
        Check if this handler can handle the given event.

        Default implementation returns True for all events.
        Override in subclasses to filter events.

        Args:
            event: The domain event to check

        Returns:
            True if handler can handle this event type
        """
        return True
