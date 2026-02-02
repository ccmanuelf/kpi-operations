# ADR 002: Domain Events Infrastructure

## Status
Accepted

## Date
2025-02-01

## Context

The platform needs to:
- Track significant state changes for audit compliance
- Enable event-driven integrations (notifications, analytics)
- Support future event sourcing capabilities
- Decouple components for better maintainability

## Decision

Implement a **Domain Events** infrastructure with:

### Event Model
```python
class DomainEvent(BaseModel):
    event_id: str  # UUID for deduplication
    event_type: str  # e.g., "work_order.status_changed"
    aggregate_id: str
    aggregate_type: str
    occurred_at: datetime
    client_id: Optional[str]
    triggered_by: Optional[int]
```

### Collect/Flush Pattern
Events are collected during transactions and flushed after commit:
```
Service → event_bus.collect(event) → [Transaction Commit] → event_bus.flush() → Handlers
```

This ensures:
- No events published for rolled-back transactions
- Events are consistent with committed state

### EVENT_STORE Persistence
All events are persisted to `EVENT_STORE` table for:
- Audit trail
- Event replay
- Analytics
- Debugging

### Key Events

| Event | Trigger |
|-------|---------|
| `WorkOrderStatusChanged` | Workflow transition |
| `ProductionEntryCreated` | New production entry |
| `QualityInspectionRecorded` | Quality check |
| `HoldCreated` | WIP hold initiated |
| `HoldResumed` | Hold released |
| `KPIThresholdViolated` | Alert condition |

### Handler Types

1. **Sync handlers**: Run before HTTP response (audit, validation)
2. **Async handlers**: Run after response (notifications, analytics)

## Implementation

```
backend/events/
  base.py              # DomainEvent, EventHandler
  bus.py               # EventBus (singleton)
  domain_events.py     # All event definitions
  session_hooks.py     # SQLAlchemy integration
  handlers/
    workflow_handlers.py
    notification_handlers.py
    analytics_handlers.py
```

## Consequences

### Positive
- Audit trail for compliance
- Loose coupling between components
- Easy to add new handlers
- Foundation for event sourcing

### Negative
- Additional complexity
- Need to manage event schema evolution
- Async handlers require careful error handling

## Related
- ADR 001: Service Layer Pattern
- ADR 003: CRUD Organization
