"""
SQLAlchemy Session Hooks for Event Bus
Phase 3: Domain Events Infrastructure

Provides automatic event flushing after successful commits
and event discarding on rollbacks.
"""

from sqlalchemy import event
import logging

from backend.events.bus import get_event_bus


logger = logging.getLogger(__name__)


def setup_session_hooks(session_factory) -> None:
    """
    Set up SQLAlchemy event listeners for automatic event handling.

    This enables the collect/flush pattern:
    - Events collected during transaction
    - Flushed after successful commit
    - Discarded on rollback

    Args:
        session_factory: SQLAlchemy session factory or Session class
    """

    @event.listens_for(session_factory, "after_commit")
    def after_commit(session):
        """Flush collected events after successful commit."""
        bus = get_event_bus()
        count = bus.flush_collected()
        if count > 0:
            logger.debug(f"Flushed {count} events after commit")

    @event.listens_for(session_factory, "after_rollback")
    def after_rollback(session):
        """Discard collected events on rollback."""
        bus = get_event_bus()
        count = bus.discard_collected()
        if count > 0:
            logger.debug(f"Discarded {count} events after rollback")


