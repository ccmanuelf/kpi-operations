/**
 * Excel Export Utility for Simulation Results
 *
 * Provides functionality to export simulation results to Excel format
 * using the ExcelJS library.
 */

import ExcelJS from 'exceljs'
import type {
  SimulationOutputBlocks,
  DailySummary,
  FreeCapacity,
  StationPerformance,
  WeeklyDemandCapacity,
  PerProductSummary,
  BundleMetrics,
  RebalancingSuggestion,
  AssumptionLog
} from '@/types/simulationV2'

interface ExportOptions {
  filename?: string
  includeAssumptions?: boolean
  includeFormulas?: boolean
}

/**
 * Format a date for display in Excel
 */
function formatDate(date: Date): string {
  return date.toISOString().split('T')[0]
}

/**
 * Format a number to a fixed decimal places
 */
function formatNumber(value: number | undefined | null, decimals: number = 2): number | string {
  if (value === undefined || value === null) return ''
  return Number(value.toFixed(decimals))
}

/**
 * Create Daily Summary worksheet data
 */
function createDailySummaryData(summary: DailySummary): (string | number)[][] {
  return [
    ['Daily Summary'],
    [''],
    ['Metric', 'Value', 'Unit'],
    ['Daily Throughput', formatNumber(summary.daily_throughput_pcs, 0), 'pieces'],
    ['Daily Demand', formatNumber(summary.daily_demand_pcs, 0), 'pieces'],
    ['Daily Coverage', formatNumber(summary.daily_coverage_pct, 1), '%'],
    ['Total Shifts per Day', summary.total_shifts_per_day, 'shifts'],
    ['Daily Planned Hours', formatNumber(summary.daily_planned_hours, 1), 'hours'],
    ['Bundles Processed per Day', formatNumber(summary.bundles_processed_per_day, 0), 'bundles'],
    ['Bundle Size', formatNumber(summary.bundle_size_pcs, 0), 'pieces'],
    ['Avg Cycle Time', formatNumber(summary.avg_cycle_time_min, 2), 'minutes'],
    ['Avg WIP', formatNumber(summary.avg_wip_pcs, 0), 'pieces']
  ]
}

/**
 * Create Free Capacity worksheet data
 */
function createFreeCapacityData(capacity: FreeCapacity): (string | number)[][] {
  return [
    ['Free Capacity Analysis'],
    [''],
    ['Metric', 'Value', 'Unit'],
    ['Daily Max Capacity', formatNumber(capacity.daily_max_capacity_pcs, 0), 'pieces'],
    ['Demand Usage', formatNumber(capacity.demand_usage_pct, 1), '%'],
    ['Free Line Hours per Day', formatNumber(capacity.free_line_hours_per_day, 1), 'hours'],
    ['Equivalent Free Operators', formatNumber(capacity.equivalent_free_operators_full_shift, 1), 'operators']
  ]
}

/**
 * Create Station Performance worksheet data
 */
function createStationPerformanceData(stations: StationPerformance[]): (string | number | boolean)[][] {
  const headers = [
    'Product', 'Step', 'Operation', 'Machine/Tool', 'Operators',
    'Utilization (%)', 'Queue Wait (min)', 'Is Bottleneck', 'Is Donor'
  ]

  const data: (string | number | boolean)[][] = [
    ['Station Performance'],
    [''],
    headers
  ]

  stations.forEach(station => {
    data.push([
      station.product,
      station.step,
      station.operation,
      station.machine_tool,
      station.operators,
      formatNumber(station.util_pct, 1),
      formatNumber(station.queue_wait_time_min, 2),
      station.is_bottleneck ? 'Yes' : 'No',
      station.is_donor ? 'Yes' : 'No'
    ])
  })

  return data
}

/**
 * Create Weekly Demand vs Capacity worksheet data
 */
function createWeeklyCapacityData(weekly: WeeklyDemandCapacity[]): (string | number)[][] {
  const headers = [
    'Product', 'Weekly Demand (pcs)', 'Max Weekly Capacity (pcs)',
    'Coverage (%)', 'Status'
  ]

  const data: (string | number)[][] = [
    ['Weekly Demand vs Capacity'],
    [''],
    headers
  ]

  weekly.forEach(row => {
    data.push([
      row.product,
      formatNumber(row.weekly_demand_pcs, 0),
      formatNumber(row.max_weekly_capacity_pcs, 0),
      formatNumber(row.demand_coverage_pct, 1),
      row.status
    ])
  })

  return data
}

/**
 * Create Per Product Summary worksheet data
 */
function createPerProductData(products: PerProductSummary[]): (string | number)[][] {
  const headers = [
    'Product', 'Bundle Size', 'Mix %', 'Daily Demand',
    'Daily Throughput', 'Coverage (%)', 'Weekly Demand', 'Weekly Throughput'
  ]

  const data: (string | number)[][] = [
    ['Per Product Summary'],
    [''],
    headers
  ]

  products.forEach(product => {
    data.push([
      product.product,
      formatNumber(product.bundle_size_pcs, 0),
      formatNumber(product.mix_share_pct, 1),
      formatNumber(product.daily_demand_pcs, 0),
      formatNumber(product.daily_throughput_pcs, 0),
      formatNumber(product.daily_coverage_pct, 1),
      formatNumber(product.weekly_demand_pcs, 0),
      formatNumber(product.weekly_throughput_pcs, 0)
    ])
  })

  return data
}

/**
 * Create Bundle Metrics worksheet data
 */
function createBundleMetricsData(bundles: BundleMetrics[]): (string | number)[][] {
  const headers = [
    'Product', 'Bundle Size', 'Bundles/Day',
    'Avg in System', 'Max in System', 'Avg Cycle Time (min)'
  ]

  const data: (string | number)[][] = [
    ['Bundle Metrics'],
    [''],
    headers
  ]

  bundles.forEach(bundle => {
    data.push([
      bundle.product,
      formatNumber(bundle.bundle_size_pcs, 0),
      formatNumber(bundle.bundles_arriving_per_day, 1),
      formatNumber(bundle.avg_bundles_in_system, 1),
      formatNumber(bundle.max_bundles_in_system, 0),
      formatNumber(bundle.avg_bundle_cycle_time_min, 1)
    ])
  })

  return data
}

/**
 * Create Rebalancing Suggestions worksheet data
 */
function createRebalancingData(suggestions: RebalancingSuggestion[]): (string | number)[][] {
  const headers = [
    'Product', 'Step', 'Operation', 'Machine',
    'Ops Before', 'Ops After', 'Util Before (%)', 'Util After (%)',
    'Role', 'Recommendation'
  ]

  const data: (string | number)[][] = [
    ['Rebalancing Suggestions'],
    [''],
    headers
  ]

  if (suggestions.length === 0) {
    data.push(['No rebalancing needed - line is well balanced'])
    return data
  }

  suggestions.forEach(suggestion => {
    data.push([
      suggestion.product,
      suggestion.step,
      suggestion.operation,
      suggestion.machine_tool,
      suggestion.operators_before,
      suggestion.operators_after,
      formatNumber(suggestion.util_before_pct, 1),
      formatNumber(suggestion.util_after_pct, 1),
      suggestion.role,
      suggestion.comment
    ])
  })

  return data
}

/**
 * Create Assumptions Log worksheet data
 */
function createAssumptionsData(log: AssumptionLog): (string | number)[][] {
  const data: (string | number)[][] = [
    ['Simulation Assumptions & Configuration'],
    [''],
    ['Configuration'],
    ['Engine Version', log.simulation_engine_version],
    ['Mode', log.configuration_mode],
    ['Timestamp', log.timestamp],
    [''],
    ['Formulas Used'],
  ]

  Object.entries(log.formula_implementations).forEach(([key, formula]) => {
    data.push([key, formula])
  })

  data.push([''])
  data.push(['Limitations & Caveats'])

  log.limitations_and_caveats.forEach(caveat => {
    data.push([caveat])
  })

  return data
}

/**
 * Helper: add rows from array-of-arrays data to a worksheet
 */
function addSheetData(workbook: ExcelJS.Workbook, sheetName: string, data: (string | number | boolean)[][]): void {
  const worksheet = workbook.addWorksheet(sheetName)
  data.forEach(row => {
    worksheet.addRow(row)
  })
}

/**
 * Helper: trigger browser download of workbook
 */
async function downloadWorkbook(workbook: ExcelJS.Workbook, filename: string): Promise<void> {
  const buffer = await workbook.xlsx.writeBuffer()
  const blob = new Blob([buffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

/**
 * Export simulation results to Excel file
 *
 * @param results - The simulation output blocks to export
 * @param options - Export options (filename, what to include)
 */
export async function exportSimulationToExcel(
  results: SimulationOutputBlocks,
  options: ExportOptions = {}
): Promise<void> {
  const {
    filename = `simulation_results_${formatDate(new Date())}.xlsx`,
    includeAssumptions = true
  } = options

  const workbook = new ExcelJS.Workbook()

  if (results.daily_summary) {
    addSheetData(workbook, 'Daily Summary', createDailySummaryData(results.daily_summary))
  }

  if (results.free_capacity) {
    addSheetData(workbook, 'Free Capacity', createFreeCapacityData(results.free_capacity))
  }

  if (results.station_performance && results.station_performance.length > 0) {
    addSheetData(workbook, 'Station Performance', createStationPerformanceData(results.station_performance))
  }

  if (results.weekly_demand_capacity && results.weekly_demand_capacity.length > 0) {
    addSheetData(workbook, 'Weekly Capacity', createWeeklyCapacityData(results.weekly_demand_capacity))
  }

  if (results.per_product_summary && results.per_product_summary.length > 0) {
    addSheetData(workbook, 'Per Product', createPerProductData(results.per_product_summary))
  }

  if (results.bundle_metrics && results.bundle_metrics.length > 0) {
    addSheetData(workbook, 'Bundle Metrics', createBundleMetricsData(results.bundle_metrics))
  }

  if (results.rebalancing_suggestions) {
    addSheetData(workbook, 'Rebalancing', createRebalancingData(results.rebalancing_suggestions))
  }

  if (includeAssumptions && results.assumption_log) {
    addSheetData(workbook, 'Assumptions', createAssumptionsData(results.assumption_log))
  }

  await downloadWorkbook(workbook, filename)
}

/**
 * Export operations configuration to Excel
 */
export async function exportOperationsToExcel(
  operations: Array<{
    product: string
    step: number
    operation: string
    machine_tool: string
    sam_min: number
    sequence?: string
    grouping?: string
    operators?: number
    variability?: string
    rework_pct?: number
    grade_pct?: number
    fpd_pct?: number
  }>,
  filename: string = `operations_${formatDate(new Date())}.xlsx`
): Promise<void> {
  const headers = [
    'Product', 'Step', 'Operation', 'Machine/Tool', 'SAM (min)',
    'Sequence', 'Grouping', 'Operators', 'Variability',
    'Rework %', 'Grade %', 'FPD %'
  ]

  const data = [headers]

  operations.forEach(op => {
    data.push([
      op.product,
      op.step,
      op.operation,
      op.machine_tool,
      op.sam_min,
      op.sequence || '',
      op.grouping || '',
      op.operators || 1,
      op.variability || 'triangular',
      op.rework_pct || 0,
      op.grade_pct || 85,
      op.fpd_pct || 15
    ])
  })

  const workbook = new ExcelJS.Workbook()
  addSheetData(workbook, 'Operations', data)
  await downloadWorkbook(workbook, filename)
}

/**
 * Export demand configuration to Excel
 */
export async function exportDemandToExcel(
  demands: Array<{
    product: string
    bundle_size: number
    daily_demand?: number | null
    weekly_demand?: number | null
    mix_share_pct?: number | null
  }>,
  mode: 'demand-driven' | 'mix-driven',
  filename: string = `demand_${formatDate(new Date())}.xlsx`
): Promise<void> {
  const headers = mode === 'demand-driven'
    ? ['Product', 'Bundle Size', 'Daily Demand', 'Weekly Demand']
    : ['Product', 'Bundle Size', 'Mix Share %']

  const data: (string | number)[][] = [headers]

  demands.forEach(d => {
    if (mode === 'demand-driven') {
      data.push([
        d.product,
        d.bundle_size,
        d.daily_demand || '',
        d.weekly_demand || ''
      ])
    } else {
      data.push([
        d.product,
        d.bundle_size,
        formatNumber(d.mix_share_pct, 1)
      ])
    }
  })

  const workbook = new ExcelJS.Workbook()
  addSheetData(workbook, 'Demand', data)
  await downloadWorkbook(workbook, filename)
}

export default {
  exportSimulationToExcel,
  exportOperationsToExcel,
  exportDemandToExcel
}
