"""Audit trail: entity-level change capture.

See docs/superpowers/specs/2026-08-11-audit-trail-design.md.
"""

from backend.audit.context import audit_suppressed

__all__ = ["audit_suppressed"]
