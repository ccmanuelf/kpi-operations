"""Routes still awaiting a response model. SHRINKS ONLY."""

ALLOWLIST = {
    "DELETE /api/v2/simulation/scenarios/{scenario_id}",
    "GET /api/capacity/kpi/variance",
    "POST /api/attendance/bulk",
    "POST /api/attendance/mark-all-present",
    "POST /api/auth/change-password",
    "POST /api/auth/forgot-password",
    "POST /api/auth/reset-password",
    "POST /api/capacity/scenarios/compare",
    "POST /api/defect-types/upload/{client_id}",
    "POST /api/floating-pool/simulation/optimize-allocation",
    "POST /api/floating-pool/simulation/shift-coverage",
    "POST /api/hold-catalogs/seed-defaults",
    "POST /api/reports/email-config/test",
    "POST /api/reports/send-manual",
    "POST /api/workflow/bulk-transition",
    "POST /api/workflow/config/{client_id}/apply-template",
    "POST /api/workflow/work-orders/{work_order_id}/transition",
    "POST /api/workflow/work-orders/{work_order_id}/validate",
    "PUT /api/kpi-thresholds",
    "PUT /api/workflow/config/{client_id}",
}
