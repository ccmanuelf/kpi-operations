"""Registers every API router on the FastAPI app, in order."""

from fastapi import FastAPI

from backend.routes import (
    attendance_router,
    coverage_router,
    quality_router,
    defect_router,
    reports_router,
    health_router,
    analytics_router,
    predictions_router,
    qr_router,
    preferences_router,
    filters_router,
    auth_router,
    users_router,
    production_router,
    import_logs_router,
    kpi_router,
    kpi_thresholds_router,
    downtime_router,
    availability_router,
    holds_router,
    wip_aging_router,
    jobs_router,
    work_order_jobs_router,
    work_orders_router,
    client_work_orders_router,
    clients_router,
    client_config_router,
    employees_router,
    client_employees_router,
    floating_pool_router,
    client_floating_pool_router,
    part_opportunities_router,
    reference_router,
    data_completeness_router,
    my_shift_router,
    alerts_router,
    workflow_router,
    simulation_v2_router,
    simulation_scenarios_router,
    simulation_calibration_router,
    database_config_router,
    cache_router,
    capacity_router,
)
from backend.routes.defect_type_catalog import router as defect_type_catalog_router
from backend.routes.hold_catalogs import router as hold_catalogs_router
from backend.routes.shifts import router as shifts_router
from backend.routes.break_times import router as break_times_router
from backend.routes.calendar import router as calendar_router
from backend.routes.production_lines import router as production_lines_router
from backend.routes.equipment import router as equipment_router
from backend.routes.employee_line_assignments import router as employee_line_assignments_router
from backend.routes.plan_vs_actual import router as plan_vs_actual_router
from backend.routes.export import router as export_router
from backend.routes.onboarding import router as onboarding_router
from backend.endpoints.csv_upload import router as csv_upload_router
from backend.routes.calculation_assumptions import router as calculation_assumptions_router
from backend.routes.metric_results import router as metric_results_router
from backend.routes.dual_view_calculate import router as dual_view_calculate_router


def register_routers(app: FastAPI) -> None:
    # ============================================================================
    # Register health check and monitoring routes
    # ============================================================================
    app.include_router(health_router)

    # ============================================================================
    # Register authentication routes
    # ============================================================================
    app.include_router(auth_router)

    # ============================================================================
    # Register user management routes
    # ============================================================================
    app.include_router(users_router)

    # ============================================================================
    # Register production routes
    # ============================================================================
    app.include_router(production_router)
    app.include_router(import_logs_router)

    # ============================================================================
    # Register KPI routes
    # ============================================================================
    app.include_router(kpi_router)
    app.include_router(kpi_thresholds_router)

    # ============================================================================
    # Register reference data routes (before shifts_router so /shifts/active
    # is matched before the parameterized /{shift_id} route)
    # ============================================================================
    app.include_router(reference_router)

    # ============================================================================
    # Register shift management routes
    # ============================================================================
    app.include_router(shifts_router)
    app.include_router(break_times_router)
    app.include_router(calendar_router)

    # ============================================================================
    # Register production line topology routes
    # ============================================================================
    app.include_router(production_lines_router)
    app.include_router(equipment_router)
    app.include_router(employee_line_assignments_router)

    # ============================================================================
    # Register downtime routes
    # ============================================================================
    app.include_router(downtime_router)
    app.include_router(availability_router)

    # ============================================================================
    # Register WIP holds routes
    # ============================================================================
    app.include_router(holds_router)
    app.include_router(wip_aging_router)
    app.include_router(hold_catalogs_router)

    # ============================================================================
    # Register job routes
    # ============================================================================
    app.include_router(jobs_router)
    app.include_router(work_order_jobs_router)

    # ============================================================================
    # Register work order routes
    # ============================================================================
    app.include_router(work_orders_router)
    app.include_router(client_work_orders_router)

    # ============================================================================
    # Register client routes
    # ============================================================================
    app.include_router(clients_router)

    # ============================================================================
    # Register client configuration routes (Phase 7.2 - Client-Level Overrides)
    # ============================================================================
    app.include_router(client_config_router)

    # ============================================================================
    # Register employee routes
    # ============================================================================
    app.include_router(employees_router)
    app.include_router(client_employees_router)

    # ============================================================================
    # Register floating pool routes
    # ============================================================================
    app.include_router(floating_pool_router)
    app.include_router(client_floating_pool_router)

    # ============================================================================
    # Register part opportunities routes
    # ============================================================================
    app.include_router(part_opportunities_router)

    # (reference_router registered earlier — before shifts_router)

    # ============================================================================
    # Register data completeness routes
    # ============================================================================
    app.include_router(data_completeness_router)

    # ============================================================================
    # Register My Shift routes (operator personalized dashboard)
    # ============================================================================
    app.include_router(my_shift_router)

    # ============================================================================
    # Phase 10: Register intelligent alerts routes
    # ============================================================================
    app.include_router(alerts_router)

    # ============================================================================
    # Phase 10: Register workflow management routes
    # ============================================================================
    app.include_router(workflow_router)

    # ============================================================================
    # Simulation v2.0: Ephemeral production line simulation (no DB dependencies)
    # ============================================================================
    app.include_router(simulation_v2_router)
    app.include_router(simulation_scenarios_router)
    app.include_router(simulation_calibration_router)

    # ============================================================================
    # Register CSV upload routes for all resources
    # ============================================================================
    app.include_router(csv_upload_router)

    # ============================================================================
    # Register attendance tracking routes
    # ============================================================================
    app.include_router(attendance_router)

    # ============================================================================
    # Register shift coverage routes
    # ============================================================================
    app.include_router(coverage_router)

    # ============================================================================
    # Register quality inspection routes
    # ============================================================================
    app.include_router(quality_router)

    # ============================================================================
    # Register defect detail routes
    # ============================================================================
    app.include_router(defect_router)

    # ============================================================================
    # Register comprehensive report generation routes
    # ============================================================================
    app.include_router(reports_router)

    # ============================================================================
    # Register analytics and prediction routes
    # ============================================================================
    app.include_router(analytics_router)

    # ============================================================================
    # Phase 5: Register comprehensive predictions routes
    # ============================================================================
    app.include_router(predictions_router)

    # ============================================================================
    # Phase 6: Register QR code routes
    # ============================================================================
    app.include_router(qr_router)

    # ============================================================================
    # Phase 7: Register user preferences routes
    # ============================================================================
    app.include_router(preferences_router)

    # ============================================================================
    # Phase 8: Register saved filters routes
    # ============================================================================
    app.include_router(filters_router)

    # ============================================================================
    # Phase 9: Register defect type catalog routes (client-specific defect types)
    # ============================================================================
    app.include_router(defect_type_catalog_router)

    # ============================================================================
    # Phase 12: Register database configuration routes (Admin only)
    # ============================================================================
    app.include_router(database_config_router)

    # ============================================================================
    # Phase A.1: Register cache management routes
    # ============================================================================
    app.include_router(cache_router)

    # ============================================================================
    # Phase B.3: Register capacity planning routes
    # ============================================================================
    app.include_router(capacity_router)

    # ============================================================================
    # Sprint 3: Plan vs Actual comparison
    # ============================================================================
    app.include_router(plan_vs_actual_router)

    # ============================================================================
    # Sprint 4: CSV/XLSX export routes
    # ============================================================================
    app.include_router(export_router)

    # ============================================================================
    # Sprint 5: Onboarding status routes
    # ============================================================================
    app.include_router(onboarding_router)

    # ============================================================================
    # Dual-View Architecture Phase 2: Calculation Assumption Registry
    # ============================================================================
    app.include_router(calculation_assumptions_router)

    # ============================================================================
    # Dual-View Architecture Phase 4: Inspector API for metric calculation results
    # ============================================================================
    app.include_router(metric_results_router)

    # ============================================================================
    # Dual-View Architecture Phase 4c: On-demand calculation endpoints
    # ============================================================================
    app.include_router(dual_view_calculate_router)

    # ============================================================================
    # NOTE: Report routes are now in routes/reports.py with proper authentication
    # See: app.include_router(reports_router) above
    # ============================================================================
