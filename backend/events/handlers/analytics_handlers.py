"""
Analytics Event Handlers
Phase 3: Domain Events Infrastructure

Observability hooks for analytics-related domain events. These handlers
record event occurrences at debug level for tracing; aggregate metrics are
computed on-read by routes/kpi/ from the underlying entry tables, not
pre-aggregated here.
"""

import logging
from backend.events.base import DomainEvent, EventHandler
from backend.events.domain_events import (
    ProductionEntryCreated,
    ProductionEntryUpdated,
    QualityInspectionRecorded,
    QualityDefectReported,
)

logger = logging.getLogger(__name__)


class ProductionMetricsHandler(EventHandler):
    """Observability hook for production entry events."""

    def __init__(self) -> None:
        super().__init__(is_async=False, priority=50)

    async def handle(self, event: DomainEvent) -> None:
        if isinstance(event, ProductionEntryCreated):
            await self._handle_entry_created(event)
        elif isinstance(event, ProductionEntryUpdated):
            await self._handle_entry_updated(event)

    async def _handle_entry_created(self, event: ProductionEntryCreated) -> None:
        logger.debug(
            f"METRICS: Production entry created - "
            f"{event.units_produced} units on {event.production_date} "
            f"(efficiency: {event.efficiency_percentage}%)"
        )

    async def _handle_entry_updated(self, event: ProductionEntryUpdated) -> None:
        logger.debug(
            f"METRICS: Production entry {event.aggregate_id} updated - " f"fields: {list(event.changed_fields.keys())}"
        )


class QualityMetricsHandler(EventHandler):
    """Observability hook for quality inspection and defect events."""

    def __init__(self) -> None:
        super().__init__(is_async=False, priority=50)

    async def handle(self, event: DomainEvent) -> None:
        if isinstance(event, QualityInspectionRecorded):
            await self._handle_inspection(event)
        elif isinstance(event, QualityDefectReported):
            await self._handle_defect(event)

    async def _handle_inspection(self, event: QualityInspectionRecorded) -> None:
        result = "PASSED" if event.passed else "FAILED"
        logger.debug(
            f"METRICS: Quality inspection {result} for {event.aggregate_id} "
            f"(defects: {event.defect_count}, scrap: {event.scrap_count})"
        )

    async def _handle_defect(self, event: QualityDefectReported) -> None:
        logger.debug(
            f"METRICS: Defect reported - type: {event.defect_type}, "
            f"quantity: {event.quantity}, severity: {event.severity}"
        )
