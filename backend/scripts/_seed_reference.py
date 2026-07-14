"""
Reference-data builders for the demo-client seeder: per-client catalogs
(hold status/reason, defect type), the config layer (ClientConfig,
KPIThreshold, AlertConfig), and the one GLOBAL (no client_id) seed
(dashboard widget defaults + metric-dependency catalog).

No behavior change from the pre-split version — this is a pure move.
"""

from sqlalchemy.orm import Session

_HOLD_STATUSES = [
    ("PENDING_HOLD_APPROVAL", "Pending Hold Approval", 1),
    ("ON_HOLD", "On Hold", 2),
    ("PENDING_RESUME_APPROVAL", "Pending Resume Approval", 3),
    ("RESUMED", "Resumed", 4),
    ("RELEASED", "Released", 5),
    ("CANCELLED", "Cancelled", 6),
    ("SCRAPPED", "Scrapped", 7),
]
_HOLD_REASONS = [
    ("QUALITY_ISSUE", "Quality Issue", 1),
    ("MATERIAL_SHORTAGE", "Material Shortage", 2),
    ("MATERIAL_INSPECTION", "Material Inspection", 3),
    ("ENGINEERING_REVIEW", "Engineering Review", 4),
    ("CUSTOMER_REQUEST", "Customer Request", 5),
    ("CAPACITY_CONSTRAINT", "Capacity Constraint", 6),
]
_DEFECT_TYPES = [
    ("STITCH", "Stitching", "SEWING", "MAJOR"),
    ("FABRIC", "Fabric Defect", "MATERIAL", "MAJOR"),
    ("MEASURE", "Measurement", "DIMENSIONAL", "MINOR"),
    ("COLOR", "Color Shade", "VISUAL", "MINOR"),
    ("STAIN", "Stain", "VISUAL", "MINOR"),
]
_KPI_THRESHOLDS = [
    ("efficiency", 85.0, 75.0, 60.0, "%", "Y"),
    ("performance", 95.0, 85.0, 70.0, "%", "Y"),
    ("quality_rate", 99.0, 97.0, 95.0, "%", "Y"),
    ("oee", 85.0, 75.0, 60.0, "%", "Y"),
    ("availability", 90.0, 80.0, 70.0, "%", "Y"),
    ("otd", 95.0, 90.0, 80.0, "%", "Y"),
]
_ALERT_CONFIGS = [
    ("efficiency", 75.0, 60.0),
    ("otd", 90.0, 80.0),
    ("quality", 97.0, 95.0),
]
_WIDGET_DEFAULTS = [
    ("admin", "kpi_summary", "KPI Summary", 1, True, '{"refreshInterval": 300}'),
    ("admin", "production_chart", "Production Chart", 2, True, '{"chartType": "bar"}'),
    ("admin", "quality_metrics", "Quality Metrics", 3, True, "{}"),
    ("admin", "alerts_panel", "Alerts Panel", 4, True, "{}"),
    ("admin", "efficiency_gauge", "Efficiency Gauge", 5, True, "{}"),
    ("supervisor", "production_chart", "Production Chart", 1, True, '{"chartType": "line"}'),
    ("supervisor", "quality_metrics", "Quality Metrics", 2, True, "{}"),
    ("supervisor", "attendance_summary", "Attendance Summary", 3, True, "{}"),
    ("supervisor", "alerts_panel", "Alerts Panel", 4, True, "{}"),
    ("operator", "my_production", "My Production", 1, True, "{}"),
    ("operator", "shift_summary", "Shift Summary", 2, True, "{}"),
    ("operator", "quality_entry", "Quality Entry", 3, True, "{}"),
]


def seed_catalogs(session: Session, client_id: str) -> None:
    """Idempotent per-client hold-status/hold-reason/defect-type catalogs."""
    from backend.orm.hold_status_catalog import HoldStatusCatalog
    from backend.orm.hold_reason_catalog import HoldReasonCatalog

    if session.query(HoldStatusCatalog).filter_by(client_id=client_id).first() is None:
        for code, name, order in _HOLD_STATUSES:
            session.add(
                HoldStatusCatalog(
                    client_id=client_id,
                    status_code=code,
                    display_name=name,
                    is_default=True,
                    is_active=True,
                    sort_order=order,
                )
            )
    if session.query(HoldReasonCatalog).filter_by(client_id=client_id).first() is None:
        for code, name, order in _HOLD_REASONS:
            session.add(
                HoldReasonCatalog(
                    client_id=client_id,
                    reason_code=code,
                    display_name=name,
                    is_default=True,
                    is_active=True,
                    sort_order=order,
                )
            )
    from backend.orm.defect_type_catalog import DefectTypeCatalog

    if session.query(DefectTypeCatalog).filter_by(client_id=client_id).first() is None:
        for code, name, category, severity in _DEFECT_TYPES:
            session.add(
                DefectTypeCatalog(
                    defect_type_id=f"DEFECT-{client_id}-{code}",
                    client_id=client_id,
                    defect_code=code,
                    defect_name=name,
                    category=category,
                    severity_default=severity,
                )
            )
    session.flush()


def seed_config_layer(session: Session, client_id: str) -> None:
    """Idempotent per-client ClientConfig, KPIThreshold set, and AlertConfig set."""
    from backend.orm.client_config import ClientConfig
    from backend.orm.kpi_threshold import KPIThreshold
    from backend.orm.alert import AlertConfig

    if session.query(ClientConfig).filter_by(client_id=client_id).first() is None:
        if client_id == "DEMO-HYBRID":
            # Customized workflow: closes at completion (no separate SHIPPED
            # gate) — exercises the non-default workflow_statuses path.
            session.add(
                ClientConfig(
                    client_id=client_id,
                    workflow_statuses='["RECEIVED", "RELEASED", "IN_PROGRESS", "COMPLETED", "CLOSED"]',
                    workflow_closure_trigger="at_completion",
                )
            )
        else:
            session.add(ClientConfig(client_id=client_id))  # all targets have credible defaults
    if session.query(KPIThreshold).filter_by(client_id=client_id).first() is None:
        for kpi_key, target, warning, critical, unit, higher in _KPI_THRESHOLDS:
            session.add(
                KPIThreshold(
                    threshold_id=f"KPI-TH-{client_id}-{kpi_key.upper()}",
                    client_id=client_id,
                    kpi_key=kpi_key,
                    target_value=target,
                    warning_threshold=warning,
                    critical_threshold=critical,
                    unit=unit,
                    higher_is_better=higher,
                )
            )
    if session.query(AlertConfig).filter_by(client_id=client_id).first() is None:
        for alert_type, warning, critical in _ALERT_CONFIGS:
            session.add(
                AlertConfig(
                    config_id=f"ALERT-CFG-{client_id}-{alert_type.upper()}",
                    client_id=client_id,
                    alert_type=alert_type,
                    enabled=True,
                    warning_threshold=warning,
                    critical_threshold=critical,
                )
            )
    session.flush()


def seed_global_defaults(session: Session) -> None:
    """Idempotent GLOBAL (no client_id) seeds: dashboard widget defaults by
    role, and the canonical metric→assumption calculation dependencies. Call
    once from main(), before the per-client loop."""
    from backend.orm.user_preferences import DashboardWidgetDefaults

    if session.query(DashboardWidgetDefaults).first() is None:
        for role, widget_key, widget_name, w_order, visible, w_config in _WIDGET_DEFAULTS:
            session.add(
                DashboardWidgetDefaults(
                    role=role,
                    widget_key=widget_key,
                    widget_name=widget_name,
                    widget_order=w_order,
                    is_visible=visible,
                    default_config=w_config,
                )
            )
        session.flush()

    from backend.services.calculations.assumption_catalog import seed_metric_dependencies

    seed_metric_dependencies(session)
