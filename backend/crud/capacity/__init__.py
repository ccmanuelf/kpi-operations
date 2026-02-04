"""
Capacity Planning CRUD Operations

This module provides CRUD operations for capacity planning tables:
- Calendar: Working days, shifts, and holidays
- Production Lines: Line capacity specifications
- Orders: Planning orders for scheduling
- Standards: SAM (Standard Allowed Minutes) by operation
- BOM: Bill of Materials (header and details)
- Stock: Inventory snapshots for MRP

All operations enforce multi-tenant isolation via client_id.
"""

# Calendar operations
from backend.crud.capacity.calendar import (
    create_calendar_entry,
    get_calendar_entries,
    get_calendar_entry,
    update_calendar_entry,
    delete_calendar_entry,
    get_calendar_for_period,
)

# Production lines operations
from backend.crud.capacity.production_lines import (
    create_production_line,
    get_production_lines,
    get_production_line,
    update_production_line,
    delete_production_line,
    get_active_lines,
    get_lines_by_department,
)

# Orders operations
from backend.crud.capacity.orders import (
    create_order,
    get_orders,
    get_order,
    update_order,
    delete_order,
    get_orders_for_scheduling,
    get_orders_by_status,
    update_order_status,
)

# Production standards operations
from backend.crud.capacity.standards import (
    create_standard,
    get_standards,
    get_standard,
    update_standard,
    delete_standard,
    get_standards_by_style,
    get_total_sam_for_style,
)

# BOM operations
from backend.crud.capacity.bom import (
    create_bom_header,
    create_bom_detail,
    get_bom_header,
    get_bom_headers,
    get_bom_details,
    update_bom_header,
    update_bom_detail,
    delete_bom_header,
    delete_bom_detail,
    get_bom_for_style,
)

# Stock operations
from backend.crud.capacity.stock import (
    create_stock_snapshot,
    get_stock_snapshots,
    get_stock_snapshot,
    update_stock_snapshot,
    delete_stock_snapshot,
    get_latest_stock,
    get_available_stock,
)

__all__ = [
    # Calendar
    'create_calendar_entry',
    'get_calendar_entries',
    'get_calendar_entry',
    'update_calendar_entry',
    'delete_calendar_entry',
    'get_calendar_for_period',
    # Production lines
    'create_production_line',
    'get_production_lines',
    'get_production_line',
    'update_production_line',
    'delete_production_line',
    'get_active_lines',
    'get_lines_by_department',
    # Orders
    'create_order',
    'get_orders',
    'get_order',
    'update_order',
    'delete_order',
    'get_orders_for_scheduling',
    'get_orders_by_status',
    'update_order_status',
    # Standards
    'create_standard',
    'get_standards',
    'get_standard',
    'update_standard',
    'delete_standard',
    'get_standards_by_style',
    'get_total_sam_for_style',
    # BOM
    'create_bom_header',
    'create_bom_detail',
    'get_bom_header',
    'get_bom_headers',
    'get_bom_details',
    'update_bom_header',
    'update_bom_detail',
    'delete_bom_header',
    'delete_bom_detail',
    'get_bom_for_style',
    # Stock
    'create_stock_snapshot',
    'get_stock_snapshots',
    'get_stock_snapshot',
    'update_stock_snapshot',
    'delete_stock_snapshot',
    'get_latest_stock',
    'get_available_stock',
]
