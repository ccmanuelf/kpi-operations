"""
Justified-delay taxonomy (Cycle 2 of the reporting data-capture roadmap).

3-state model: WorkOrder.delay_classification is NULL (unclassified, default),
'justified', or 'unjustified'. Unclassified is the ABSENCE of a value — never
an enum member, never offered in UI selects. justified_delay_reason is stored
only when classification == 'justified'.

Sibling of backend/orm/downtime_taxonomy.py (Cycle 1) — same conventions.
Spec: docs/superpowers/specs/2026-08-04-justified-delay-flag-design.md
"""

from enum import Enum


class DelayClassificationEnum(str, Enum):
    """Late-order delay classification (NULL = unclassified)."""

    JUSTIFIED = "justified"
    UNJUSTIFIED = "unjustified"


class JustifiedDelayReasonEnum(str, Enum):
    """Controlled justification reasons (required iff classification is justified)."""

    CUSTOMER_REQUEST = "customer_request"
    CUSTOMER_CHANGE_ORDER = "customer_change_order"
    MATERIAL_SUPPLIER_DELAY = "material_supplier_delay"
    FORCE_MAJEURE = "force_majeure"
    UPSTREAM_HOLD = "upstream_hold"
    OTHER = "other"


SELECTABLE_DELAY_REASONS: list[str] = [r.value for r in JustifiedDelayReasonEnum]
