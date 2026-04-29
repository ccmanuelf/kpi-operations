/**
 * Default factory functions for Capacity Planning worksheet row
 * types. Shared across sub-stores; each function returns a fresh
 * default object for its corresponding worksheet.
 */

export interface CalendarEntry {
  calendar_date: string | null
  is_working_day: boolean
  shifts_available: number
  shift1_hours: number
  shift2_hours: number
  shift3_hours: number
  holiday_name: string | null
  notes: string | null
  [key: string]: unknown
}

export interface ProductionLineRow {
  line_code: string
  line_name: string
  department: string
  standard_capacity_units_per_hour: number
  max_operators: number
  efficiency_factor: number
  absenteeism_factor: number
  is_active: boolean
  notes: string | null
  [key: string]: unknown
}

export interface OrderRow {
  order_number: string
  customer_name: string
  style_model: string
  style_description: string
  order_quantity: number
  completed_quantity: number
  order_date: string | null
  required_date: string | null
  planned_start_date: string | null
  planned_end_date: string | null
  priority: string
  status: string
  order_sam_minutes: number | null
  notes: string | null
  [key: string]: unknown
}

export interface StandardRow {
  style_model: string
  operation_code: string
  operation_name: string
  department: string
  sam_minutes: number
  setup_time_minutes: number
  machine_time_minutes: number
  manual_time_minutes: number
  notes: string | null
  [key: string]: unknown
}

export interface BOMHeaderRow {
  parent_item_code: string
  parent_item_description: string
  style_model: string
  revision: string
  is_active: boolean
  notes: string | null
  components: BOMDetailRow[]
  [key: string]: unknown
}

export interface BOMDetailRow {
  component_item_code: string
  component_description: string
  quantity_per: number
  unit_of_measure: string
  waste_percentage: number
  component_type: string
  notes: string | null
  [key: string]: unknown
}

export interface StockSnapshotRow {
  snapshot_date: string | null
  item_code: string
  item_description: string
  on_hand_quantity: number
  allocated_quantity: number
  on_order_quantity: number
  available_quantity: number
  unit_of_measure: string
  location: string | null
  notes: string | null
  [key: string]: unknown
}

export interface ComponentCheckRow {
  order_id: string | number | null
  component_item_code: string
  component_description: string
  required_quantity: number
  available_quantity: number
  shortage_quantity: number
  total_component_demand: number
  status: 'AVAILABLE' | 'SHORTAGE' | 'PARTIAL' | string
  planner_notes: string | null
  notes: string | null
  [key: string]: unknown
}

export interface CapacityAnalysisRow {
  line_id: string | number | null
  line_code: string
  period_date: string | null
  required_hours: number
  available_hours: number
  utilization_percent: number
  is_bottleneck: boolean
  notes: string | null
  [key: string]: unknown
}

export interface ScheduleRow {
  schedule_detail_id: string | number | null
  order_id: string | number | null
  order_number: string
  line_id: string | number | null
  line_code: string
  scheduled_date: string | null
  planned_quantity: number
  sequence_number: number
  status: string
  notes: string | null
  [key: string]: unknown
}

export interface ScenarioRow {
  scenario_name: string
  scenario_type: string
  base_schedule_id: string | number | null
  parameters: Record<string, unknown>
  status: string
  notes: string | null
  [key: string]: unknown
}

export interface KPITrackingRow {
  kpi_name: string
  target_value: number
  actual_value: number | null
  variance_percent: number | null
  period_start: string | null
  period_end: string | null
  status: string
  notes: string | null
  [key: string]: unknown
}

export interface DashboardInputs {
  planning_horizon_days: number
  default_efficiency: number
  bottleneck_threshold: number
  shortage_alert_days: number
  auto_schedule_enabled: boolean
  [key: string]: unknown
}

export const getDefaultCalendarEntry = (): CalendarEntry => ({
  calendar_date: null,
  is_working_day: true,
  shifts_available: 1,
  shift1_hours: 8.0,
  shift2_hours: 0,
  shift3_hours: 0,
  holiday_name: null,
  notes: null,
})

export const getDefaultProductionLine = (): ProductionLineRow => ({
  line_code: '',
  line_name: '',
  department: '',
  standard_capacity_units_per_hour: 0,
  max_operators: 10,
  efficiency_factor: 0.85,
  absenteeism_factor: 0.05,
  is_active: true,
  notes: null,
})

export const getDefaultOrder = (): OrderRow => ({
  order_number: '',
  customer_name: '',
  style_model: '',
  style_description: '',
  order_quantity: 0,
  completed_quantity: 0,
  order_date: null,
  required_date: null,
  planned_start_date: null,
  planned_end_date: null,
  priority: 'NORMAL',
  status: 'DRAFT',
  order_sam_minutes: null,
  notes: null,
})

export const getDefaultStandard = (): StandardRow => ({
  style_model: '',
  operation_code: '',
  operation_name: '',
  department: '',
  sam_minutes: 0,
  setup_time_minutes: 0,
  machine_time_minutes: 0,
  manual_time_minutes: 0,
  notes: null,
})

export const getDefaultBOMHeader = (): BOMHeaderRow => ({
  parent_item_code: '',
  parent_item_description: '',
  style_model: '',
  revision: '1.0',
  is_active: true,
  notes: null,
  components: [],
})

export const getDefaultBOMDetail = (): BOMDetailRow => ({
  component_item_code: '',
  component_description: '',
  quantity_per: 1.0,
  unit_of_measure: 'EA',
  waste_percentage: 0,
  component_type: '',
  notes: null,
})

export const getDefaultStockSnapshot = (): StockSnapshotRow => ({
  snapshot_date: null,
  item_code: '',
  item_description: '',
  on_hand_quantity: 0,
  allocated_quantity: 0,
  on_order_quantity: 0,
  available_quantity: 0,
  unit_of_measure: 'EA',
  location: null,
  notes: null,
})

export const getDefaultComponentCheckRow = (): ComponentCheckRow => ({
  order_id: null,
  component_item_code: '',
  component_description: '',
  required_quantity: 0,
  available_quantity: 0,
  shortage_quantity: 0,
  total_component_demand: 0,
  status: 'AVAILABLE',
  planner_notes: null,
  notes: null,
})

export const getDefaultCapacityAnalysisRow = (): CapacityAnalysisRow => ({
  line_id: null,
  line_code: '',
  period_date: null,
  required_hours: 0,
  available_hours: 0,
  utilization_percent: 0,
  is_bottleneck: false,
  notes: null,
})

export const getDefaultScheduleRow = (): ScheduleRow => ({
  schedule_detail_id: null,
  order_id: null,
  order_number: '',
  line_id: null,
  line_code: '',
  scheduled_date: null,
  planned_quantity: 0,
  sequence_number: 0,
  status: 'SCHEDULED',
  notes: null,
})

export const getDefaultScenario = (): ScenarioRow => ({
  scenario_name: '',
  scenario_type: 'OVERTIME',
  base_schedule_id: null,
  parameters: {},
  status: 'DRAFT',
  notes: null,
})

export const getDefaultKPITrackingRow = (): KPITrackingRow => ({
  kpi_name: '',
  target_value: 0,
  actual_value: null,
  variance_percent: null,
  period_start: null,
  period_end: null,
  status: 'PENDING',
  notes: null,
})

export const getDefaultDashboardInputs = (): DashboardInputs => ({
  planning_horizon_days: 30,
  default_efficiency: 85,
  bottleneck_threshold: 90,
  shortage_alert_days: 7,
  auto_schedule_enabled: false,
})

export const defaultFactoryMap: Record<string, () => Record<string, unknown>> = {
  masterCalendar: getDefaultCalendarEntry,
  productionLines: getDefaultProductionLine,
  orders: getDefaultOrder,
  productionStandards: getDefaultStandard,
  bom: getDefaultBOMHeader,
  stockSnapshot: getDefaultStockSnapshot,
  componentCheck: getDefaultComponentCheckRow,
  capacityAnalysis: getDefaultCapacityAnalysisRow,
  productionSchedule: getDefaultScheduleRow,
  whatIfScenarios: getDefaultScenario,
  kpiTracking: getDefaultKPITrackingRow,
}
