"""
Event Bus Implementation
Phase 3: Domain Events Infrastructure

Provides event publishing and handling with:
- Collect/flush pattern for transactional consistency
- Priority-based handler execution
- Async handler support
- Error isolation
"""

from typing import List, Dict, Type, Callable, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict
import asyncio
import logging
import threading

from backend.events.base import DomainEvent, EventHandler


logger = logging.getLogger(__name__)


@dataclass
class HandlerRegistration:
    """Registration entry for an event handler."""

    handler: EventHandler
    event_type: str
    priority: int
    is_async: bool


class EventBus:
    """
    Central event bus for domain event publishing and handling.

    Features:
    - Collect/flush pattern for transactional consistency
    - Events collected during transaction, flushed after commit
    - Priority-based handler execution
    - Async handlers run after HTTP response
    - Error isolation prevents cascade failures
    """

    _instance: Optional["EventBus"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "EventBus":
        """Singleton pattern for global event bus."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the event bus (only once due to singleton)."""
        if self._initialized:
            return

        self._handlers: Dict[str, List[HandlerRegistration]] = defaultdict(list)
        self._collected_events: List[DomainEvent] = []
        self._persistence_handler: Optional[Callable] = None
        self._initialized = True

    def subscribe(self, event_type: str, handler: EventHandler, priority: int = 100, is_async: bool = False) -> None:
        """
        Subscribe a handler to an event type.

        Args:
            event_type: Event type to subscribe to (e.g., 'work_order.status_changed')
            handler: Handler instance
            priority: Lower numbers run first (default 100)
            is_async: If True, handler runs after HTTP response
        """
        registration = HandlerRegistration(handler=handler, event_type=event_type, priority=priority, is_async=is_async)
        self._handlers[event_type].append(registration)
        # Sort by priority
        self._handlers[event_type].sort(key=lambda r: r.priority)
        logger.debug(f"Subscribed handler to {event_type} with priority {priority}")

    def unsubscribe(self, event_type: str, handler: EventHandler) -> bool:
        """
        Unsubscribe a handler from an event type.

        Args:
            event_type: Event type to unsubscribe from
            handler: Handler instance to remove

        Returns:
            True if handler was found and removed
        """
        handlers = self._handlers.get(event_type, [])
        for i, reg in enumerate(handlers):
            if reg.handler is handler:
                handlers.pop(i)
                return True
        return False

    def publish(self, event: DomainEvent) -> None:
        """
        Publish an event immediately (synchronous handlers only).

        For transactional consistency, prefer collect() + flush_collected().

        Args:
            event: The domain event to publish
        """
        self._dispatch_to_handlers(event, sync_only=True)

    def collect(self, event: DomainEvent) -> None:
        """
        Collect an event for later flushing (after transaction commit).

        Events are held until flush_collected() is called.
        Use discard_collected() on rollback.

        Args:
            event: The domain event to collect
        """
        self._collected_events.append(event)
        logger.debug(f"Collected event: {event.event_type} ({event.event_id})")

    def flush_collected(self) -> int:
        """
        Flush all collected events (call after transaction commit).

        Returns:
            Number of events flushed
        """
        events = self._collected_events.copy()
        self._collected_events.clear()

        count = 0
        for event in events:
            try:
                # Persist event if handler is configured
                if self._persistence_handler:
                    self._persistence_handler(event)

                # Dispatch to handlers
                self._dispatch_to_handlers(event)
                count += 1
            except Exception as e:
                logger.error(f"Error flushing event {event.event_id}: {e}")
                # Continue with other events

        logger.debug(f"Flushed {count} events")
        return count

    def discard_collected(self) -> int:
        """
        Discard all collected events (call on transaction rollback).

        Returns:
            Number of events discarded
        """
        count = len(self._collected_events)
        self._collected_events.clear()
        logger.debug(f"Discarded {count} collected events")
        return count

    def get_collected_events(self) -> List[DomainEvent]:
        """
        Get currently collected events (for testing/debugging).

        Returns:
            List of collected events
        """
        return self._collected_events.copy()

    def set_persistence_handler(self, handler: Callable[[DomainEvent], None]) -> None:
        """
        Set a handler for persisting events to EVENT_STORE.

        Args:
            handler: Callable that persists an event
        """
        self._persistence_handler = handler

    def _dispatch_to_handlers(self, event: DomainEvent, sync_only: bool = False) -> None:
        """
        Dispatch event to registered handlers.

        Args:
            event: Event to dispatch
            sync_only: If True, skip async handlers
        """
        handlers = self._handlers.get(event.event_type, [])

        # Also check for wildcard handlers
        wildcard_handlers = self._handlers.get("*", [])
        all_handlers = handlers + wildcard_handlers

        for reg in all_handlers:
            if sync_only and reg.is_async:
                continue

            try:
                if not reg.handler.can_handle(event):
                    continue

                if reg.is_async:
                    # Schedule async handler
                    asyncio.create_task(self._run_async_handler(reg.handler, event))
                else:
                    # Run sync handler directly
                    asyncio.get_event_loop().run_until_complete(reg.handler.handle(event))
            except RuntimeError:
                # No event loop - run synchronously
                try:
                    asyncio.run(reg.handler.handle(event))
                except Exception as e:
                    logger.error(f"Handler error for {event.event_type}: {e}")
            except Exception as e:
                logger.error(f"Handler error for {event.event_type}: {e}")
                # Continue with other handlers

    async def _run_async_handler(self, handler: EventHandler, event: DomainEvent) -> None:
        """Run an async handler with error isolation."""
        try:
            await handler.handle(event)
        except Exception as e:
            logger.error(f"Async handler error for {event.event_type}: {e}")


# Global event bus instance
event_bus = EventBus()


def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    return event_bus
