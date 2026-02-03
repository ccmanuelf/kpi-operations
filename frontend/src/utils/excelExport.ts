/**
 * Excel Export Utility for Simulation Results
 *
 * Provides functionality to export simulation results to Excel format
 * using the SheetJS (xlsx) library.
 */

import * as XLSX from 'xlsx'
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
 * Export simulation results to Excel file
 *
 * @param results - The simulation output blocks to export
 * @param options - Export options (filename, what to include)
 */
export function exportSimulationToExcel(
  results: SimulationOutputBlocks,
  options: ExportOptions = {}
): void {
  const {
    filename = `simulation_results_${formatDate(new Date())}.xlsx`,
    includeAssumptions = true
  } = options

  // Create workbook
  const workbook = XLSX.utils.book_new()

  // Add Daily Summary sheet
  if (results.daily_summary) {
    const summaryData = createDailySummaryData(results.daily_summary)
    const summarySheet = XLSX.utils.aoa_to_sheet(summaryData)
    XLSX.utils.book_append_sheet(workbook, summarySheet, 'Daily Summary')
  }

  // Add Free Capacity sheet
  if (results.free_capacity) {
    const capacityData = createFreeCapacityData(results.free_capacity)
    const capacitySheet = XLSX.utils.aoa_to_sheet(capacityData)
    XLSX.utils.book_append_sheet(workbook, capacitySheet, 'Free Capacity')
  }

  // Add Station Performance sheet
  if (results.station_performance && results.station_performance.length > 0) {
    const stationData = createStationPerformanceData(results.station_performance)
    const stationSheet = XLSX.utils.aoa_to_sheet(stationData)
    XLSX.utils.book_append_sheet(workbook, stationSheet, 'Station Performance')
  }

  // Add Weekly Capacity sheet
  if (results.weekly_demand_capacity && results.weekly_demand_capacity.length > 0) {
    const weeklyData = createWeeklyCapacityData(results.weekly_demand_capacity)
    const weeklySheet = XLSX.utils.aoa_to_sheet(weeklyData)
    XLSX.utils.book_append_sheet(workbook, weeklySheet, 'Weekly Capacity')
  }

  // Add Per Product sheet
  if (results.per_product_summary && results.per_product_summary.length > 0) {
    const productData = createPerProductData(results.per_product_summary)
    const productSheet = XLSX.utils.aoa_to_sheet(productData)
    XLSX.utils.book_append_sheet(workbook, productSheet, 'Per Product')
  }

  // Add Bundle Metrics sheet
  if (results.bundle_metrics && results.bundle_metrics.length > 0) {
    const bundleData = createBundleMetricsData(results.bundle_metrics)
    const bundleSheet = XLSX.utils.aoa_to_sheet(bundleData)
    XLSX.utils.book_append_sheet(workbook, bundleSheet, 'Bundle Metrics')
  }

  // Add Rebalancing Suggestions sheet
  if (results.rebalancing_suggestions) {
    const rebalanceData = createRebalancingData(results.rebalancing_suggestions)
    const rebalanceSheet = XLSX.utils.aoa_to_sheet(rebalanceData)
    XLSX.utils.book_append_sheet(workbook, rebalanceSheet, 'Rebalancing')
  }

  // Add Assumptions sheet
  if (includeAssumptions && results.assumption_log) {
    const assumptionsData = createAssumptionsData(results.assumption_log)
    const assumptionsSheet = XLSX.utils.aoa_to_sheet(assumptionsData)
    XLSX.utils.book_append_sheet(workbook, assumptionsSheet, 'Assumptions')
  }

  // Write to file (triggers download in browser)
  XLSX.writeFile(workbook, filename)
}

/**
 * Export operations configuration to Excel
 *
 * @param operations - Array of operation configurations
 * @param filename - Output filename
 */
export function exportOperationsToExcel(
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
): void {
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

  const workbook = XLSX.utils.book_new()
  const sheet = XLSX.utils.aoa_to_sheet(data)
  XLSX.utils.book_append_sheet(workbook, sheet, 'Operations')
  XLSX.writeFile(workbook, filename)
}

/**
 * Export demand configuration to Excel
 *
 * @param demands - Array of demand configurations
 * @param mode - Demand mode ('demand-driven' or 'mix-driven')
 * @param filename - Output filename
 */
export function exportDemandToExcel(
  demands: Array<{
    product: string
    bundle_size: number
    daily_demand?: number | null
    weekly_demand?: number | null
    mix_share_pct?: number | null
  }>,
  mode: 'demand-driven' | 'mix-driven',
  filename: string = `demand_${formatDate(new Date())}.xlsx`
): void {
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

  const workbook = XLSX.utils.book_new()
  const sheet = XLSX.utils.aoa_to_sheet(data)
  XLSX.utils.book_append_sheet(workbook, sheet, 'Demand')
  XLSX.writeFile(workbook, filename)
}

export default {
  exportSimulationToExcel,
  exportOperationsToExcel,
  exportDemandToExcel
}
