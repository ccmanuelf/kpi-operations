/**
 * Default factory functions for Capacity Planning worksheet row types.
 *
 * Shared across sub-stores. Each function returns a fresh default object
 * for its corresponding worksheet type.
 */

export const getDefaultCalendarEntry = () => ({
  calendar_date: null,
  is_working_day: true,
  shifts_available: 1,
  shift1_hours: 8.0,
  shift2_hours: 0,
  shift3_hours: 0,
  holiday_name: null,
  notes: null
})

export const getDefaultProductionLine = () => ({
  line_code: '',
  line_name: '',
  department: '',
  standard_capacity_units_per_hour: 0,
  max_operators: 10,
  efficiency_factor: 0.85,
  absenteeism_factor: 0.05,
  is_active: true,
  notes: null
})

export const getDefaultOrder = () => ({
  order_number: '',
  customer_name: '',
  style_code: '',
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
  notes: null
})

export const getDefaultStandard = () => ({
  style_code: '',
  operation_code: '',
  operation_name: '',
  department: '',
  sam_minutes: 0,
  setup_time_minutes: 0,
  machine_time_minutes: 0,
  manual_time_minutes: 0,
  notes: null
})

export const getDefaultBOMHeader = () => ({
  parent_item_code: '',
  parent_item_description: '',
  style_code: '',
  revision: '1.0',
  is_active: true,
  notes: null,
  components: []
})

export const getDefaultBOMDetail = () => ({
  component_item_code: '',
  component_description: '',
  quantity_per: 1.0,
  unit_of_measure: 'EA',
  waste_percentage: 0,
  component_type: '',
  notes: null
})

export const getDefaultStockSnapshot = () => ({
  snapshot_date: null,
  item_code: '',
  item_description: '',
  on_hand_quantity: 0,
  allocated_quantity: 0,
  on_order_quantity: 0,
  available_quantity: 0,
  unit_of_measure: 'EA',
  location: null,
  notes: null
})

export const getDefaultComponentCheckRow = () => ({
  order_id: null,
  component_item_code: '',
  component_description: '',
  required_quantity: 0,
  available_quantity: 0,
  shortage_quantity: 0,
  total_component_demand: 0,
  status: 'AVAILABLE', // AVAILABLE, SHORTAGE, PARTIAL
  planner_notes: null,
  notes: null
})

export const getDefaultCapacityAnalysisRow = () => ({
  line_id: null,
  line_code: '',
  period_date: null,
  required_hours: 0,
  available_hours: 0,
  utilization_percent: 0,
  is_bottleneck: false,
  notes: null
})

export const getDefaultScheduleRow = () => ({
  schedule_detail_id: null,
  order_id: null,
  order_number: '',
  line_id: null,
  line_code: '',
  scheduled_date: null,
  planned_quantity: 0,
  sequence_number: 0,
  status: 'SCHEDULED',
  notes: null
})

export const getDefaultScenario = () => ({
  scenario_name: '',
  scenario_type: 'OVERTIME', // OVERTIME, SETUP_REDUCTION, SUBCONTRACT, NEW_LINE, THREE_SHIFT, LEAD_TIME_DELAY, ABSENTEEISM_SPIKE, MULTI_CONSTRAINT
  base_schedule_id: null,
  parameters: {},
  status: 'DRAFT',
  notes: null
})

export const getDefaultKPITrackingRow = () => ({
  kpi_name: '',
  target_value: 0,
  actual_value: null,
  variance_percent: null,
  period_start: null,
  period_end: null,
  status: 'PENDING',
  notes: null
})

export const getDefaultDashboardInputs = () => ({
  planning_horizon_days: 30,
  default_efficiency: 85,
  bottleneck_threshold: 90,
  shortage_alert_days: 7,
  auto_schedule_enabled: false
})

/**
 * Map worksheet name to its default factory function.
 */
export const defaultFactoryMap = {
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
  kpiTracking: getDefaultKPITrackingRow
}
