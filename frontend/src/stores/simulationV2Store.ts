import { defineStore } from 'pinia'
import { useNotificationStore } from '@/stores/notificationStore'
import {
  getSimulationInfo,
  validateSimulationConfig,
  runSimulation,
  runMonteCarlo,
  buildSimulationConfig,
  getDefaultOperation,
  getDefaultSchedule,
  getDefaultDemand,
  getDefaultBreakdown,
  getSampleTShirtData,
  isFirstVisit as svIsFirstVisit,
  markAsVisited,
  clearVisitedFlag,
  type SimulationMode,
  type OperationDraft,
  type ScheduleDraft,
  type DemandDraft,
  type BreakdownDraft,
} from '@/services/api/simulationV2'

export type Tab = 'operations' | 'schedule' | 'demands' | 'breakdowns' | 'results' | string

// Augment grid drafts with the synthetic `_id` the store assigns for
// row-tracking purposes. The simulationV2 module's own draft types
// stay UI-payload-only.
export type OperationRow = OperationDraft & { _id?: number }
export type DemandRow = DemandDraft & { _id?: number }
export type BreakdownRow = BreakdownDraft & { _id?: number }

export interface ValidationReport {
  is_valid?: boolean
  errors?: unknown[]
  warnings?: unknown[]
  info?: unknown[]
  [key: string]: unknown
}

export interface SimulationResults {
  [key: string]: unknown
}

export interface SimulationRunResponse {
  success?: boolean
  results?: SimulationResults
  message?: string
  validation_report?: ValidationReport
  [key: string]: unknown
}

export interface ToolInfo {
  [key: string]: unknown
}

interface SimulationState {
  toolInfo: ToolInfo | null
  operations: OperationRow[]
  schedule: ScheduleDraft
  demands: DemandRow[]
  breakdowns: BreakdownRow[]
  mode: SimulationMode
  totalDemand: number | null
  horizonDays: number
  validationReport: ValidationReport | null
  isValidating: boolean
  isRunning: boolean
  results: SimulationResults | null
  simulationMessage: string
  activeTab: Tab
  showValidationPanel: boolean
  showResultsDialog: boolean
  error: string | null
  // Monte Carlo state — opt-in N-replication mode (Deliverable 1).
  monteCarloEnabled: boolean
  monteCarloReplications: number
  monteCarloBaseSeed: number | null
  monteCarloAggregatedStats: Record<string, unknown> | null
  monteCarloDurationSeconds: number | null
}

const extractDetail = (e: unknown, fallback: string): string => {
  const ax = e as { response?: { data?: { detail?: string } }; message?: string }
  return ax?.response?.data?.detail || ax?.message || fallback
}

export const useSimulationV2Store = defineStore('simulationV2', {
  state: (): SimulationState => ({
    toolInfo: null,
    operations: [],
    schedule: getDefaultSchedule(),
    demands: [],
    breakdowns: [],
    mode: 'demand-driven',
    totalDemand: null,
    horizonDays: 1,
    validationReport: null,
    isValidating: false,
    isRunning: false,
    results: null,
    simulationMessage: '',
    activeTab: 'operations',
    showValidationPanel: false,
    showResultsDialog: false,
    error: null,
    monteCarloEnabled: false,
    monteCarloReplications: 10,
    monteCarloBaseSeed: null,
    monteCarloAggregatedStats: null,
    monteCarloDurationSeconds: null,
  }),

  getters: {
    canRun: (state): boolean =>
      state.operations.length > 0 &&
      state.demands.length > 0 &&
      !state.isRunning &&
      (!state.validationReport || state.validationReport.is_valid === true),

    products: (state): string[] =>
      [...new Set(state.operations.map((op) => op.product))].filter(Boolean),

    machineTools: (state): string[] =>
      [...new Set(state.operations.map((op) => op.machine_tool))].filter(Boolean),

    operationsByProduct: (state): Record<string, OperationRow[]> => {
      const grouped: Record<string, OperationRow[]> = {}
      for (const op of state.operations) {
        if (!grouped[op.product]) {
          grouped[op.product] = []
        }
        grouped[op.product].push(op)
      }
      for (const product in grouped) {
        grouped[product].sort((a, b) => Number(a.step) - Number(b.step))
      }
      return grouped
    },

    operationsCount: (state): number => state.operations.length,

    productsCount: (state): number =>
      new Set(state.operations.map((op) => op.product).filter(Boolean)).size,

    hasValidationErrors: (state): boolean =>
      (state.validationReport?.errors?.length ?? 0) > 0,

    hasValidationWarnings: (state): boolean =>
      (state.validationReport?.warnings?.length ?? 0) > 0,

    dailyPlannedHours: (state): number => {
      let hours = Number(state.schedule.shift1_hours) || 0
      const shiftsEnabled = Number(state.schedule.shifts_enabled)
      if (shiftsEnabled >= 2) {
        hours += Number(state.schedule.shift2_hours) || 0
      }
      if (shiftsEnabled >= 3) {
        hours += Number(state.schedule.shift3_hours) || 0
      }
      return hours
    },

    totalMixPercent: (state): number =>
      state.demands.reduce(
        (sum, d) => sum + (parseFloat(String(d.mix_share_pct ?? 0)) || 0),
        0,
      ),
  },

  actions: {
    async fetchToolInfo(): Promise<void> {
      try {
        this.toolInfo = await getSimulationInfo()
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error('Failed to fetch simulation info:', error)
        this.error = extractDetail(error, 'Failed to fetch simulation info')
        useNotificationStore().showError(this.error)
      }
    },

    addOperation(operation: OperationRow | null = null): void {
      const newOp = operation || getDefaultOperation(this.products[0] || '')
      const sameProductOps = this.operations.filter((op) => op.product === newOp.product)
      if (sameProductOps.length > 0 && !operation) {
        newOp.step = Math.max(...sameProductOps.map((op) => Number(op.step))) + 1
      }
      this.operations.push({ ...newOp, _id: Date.now() })
    },

    updateOperation(index: number, updates: Partial<OperationRow>): void {
      if (this.operations[index]) {
        Object.assign(this.operations[index], updates)
      }
    },

    removeOperation(index: number): void {
      this.operations.splice(index, 1)
    },

    importOperations(operations: Partial<OperationRow>[]): void {
      this.operations = operations.map((op, idx) => ({
        ...getDefaultOperation(),
        ...op,
        _id: Date.now() + idx,
      })) as OperationRow[]
    },

    updateSchedule(updates: Partial<ScheduleDraft>): void {
      Object.assign(this.schedule, updates)
    },

    addDemand(demand: DemandRow | null = null): void {
      const newDemand = demand || getDefaultDemand('')
      this.demands.push({ ...newDemand, _id: Date.now() })
    },

    updateDemand(index: number, updates: Partial<DemandRow>): void {
      if (this.demands[index]) {
        Object.assign(this.demands[index], updates)
      }
    },

    removeDemand(index: number): void {
      this.demands.splice(index, 1)
    },

    importDemands(demands: Partial<DemandRow>[]): void {
      this.demands = demands.map((d, idx) => ({
        ...getDefaultDemand(),
        ...d,
        _id: Date.now() + idx,
      })) as DemandRow[]
    },

    addBreakdown(breakdown: BreakdownRow | null = null): void {
      const newBreakdown = breakdown || getDefaultBreakdown('')
      this.breakdowns.push({ ...newBreakdown, _id: Date.now() })
    },

    updateBreakdown(index: number, updates: Partial<BreakdownRow>): void {
      if (this.breakdowns[index]) {
        Object.assign(this.breakdowns[index], updates)
      }
    },

    removeBreakdown(index: number): void {
      this.breakdowns.splice(index, 1)
    },

    setMode(mode: SimulationMode): void {
      this.mode = mode
      if (mode === 'demand-driven') {
        this.totalDemand = null
      }
    },

    buildConfig() {
      return buildSimulationConfig({
        operations: this.operations,
        schedule: this.schedule,
        demands: this.demands,
        breakdowns: this.breakdowns,
        mode: this.mode,
        totalDemand: this.totalDemand,
        horizonDays: this.horizonDays,
      })
    },

    async validate(): Promise<ValidationReport> {
      this.isValidating = true
      this.error = null
      this.validationReport = null

      try {
        const config = this.buildConfig()
        this.validationReport = (await validateSimulationConfig(config)) as ValidationReport
        this.showValidationPanel = true
        return this.validationReport
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error('Validation failed:', error)
        this.error = extractDetail(error, 'Validation failed')
        useNotificationStore().showError(
          this.error || 'Validation failed. Please check your configuration.',
        )
        throw error
      } finally {
        this.isValidating = false
      }
    },

    async run(): Promise<SimulationRunResponse> {
      this.isRunning = true
      this.error = null
      this.results = null
      this.simulationMessage = ''

      try {
        const config = this.buildConfig()
        const response = (await runSimulation(config)) as SimulationRunResponse

        if (response.success) {
          this.results = response.results || null
          this.simulationMessage = response.message || ''
          this.validationReport = response.validation_report || null
          this.showResultsDialog = true
        } else {
          this.validationReport = response.validation_report || null
          this.simulationMessage = response.message || ''
          this.showValidationPanel = true
        }

        return response
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error('Simulation failed:', error)
        this.error = extractDetail(error, 'Simulation failed')
        useNotificationStore().showError(
          this.error || 'Simulation failed. Please try again.',
        )
        throw error
      } finally {
        this.isRunning = false
      }
    },

    /**
     * Run the simulation in Monte Carlo mode (N replications, mean ± CI).
     * Uses `monteCarloReplications` and `monteCarloBaseSeed` from state.
     * On success, populates `results` with the `sample_run` (so existing
     * result-rendering keeps working) AND `monteCarloAggregatedStats`
     * for any UI that wants to render CI bands.
     */
    async runMonteCarloAction(): Promise<unknown> {
      this.isRunning = true
      this.error = null
      this.results = null
      this.simulationMessage = ''
      this.monteCarloAggregatedStats = null
      this.monteCarloDurationSeconds = null

      try {
        const config = this.buildConfig()
        const response = (await runMonteCarlo({
          config,
          n_replications: this.monteCarloReplications,
          base_seed: this.monteCarloBaseSeed,
        })) as {
          success?: boolean
          n_replications?: number
          total_duration_seconds?: number
          aggregated_stats?: Record<string, unknown>
          sample_run?: SimulationResults
          validation_report?: ValidationReport
          message?: string
        }

        if (response.success) {
          // Existing UI consumes `results` for rendering; expose the
          // sample run there so we don't fork the rendering paths.
          this.results = response.sample_run || null
          this.monteCarloAggregatedStats = response.aggregated_stats || null
          this.monteCarloDurationSeconds = response.total_duration_seconds ?? null
          this.simulationMessage = response.message || ''
          this.validationReport = response.validation_report || null
          this.showResultsDialog = true
        } else {
          this.validationReport = response.validation_report || null
          this.simulationMessage = response.message || ''
          this.showValidationPanel = true
        }

        return response
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error('Monte Carlo simulation failed:', error)
        this.error = extractDetail(error, 'Monte Carlo simulation failed')
        useNotificationStore().showError(
          this.error || 'Monte Carlo simulation failed. Please try again.',
        )
        throw error
      } finally {
        this.isRunning = false
      }
    },

    reset(): void {
      this.operations = []
      this.schedule = getDefaultSchedule()
      this.demands = []
      this.breakdowns = []
      this.mode = 'demand-driven'
      this.totalDemand = null
      this.horizonDays = 1
      this.validationReport = null
      this.results = null
      this.error = null
      this.simulationMessage = ''
      this.monteCarloAggregatedStats = null
      this.monteCarloDurationSeconds = null
    },

    loadConfiguration(config: {
      operations?: Partial<OperationRow>[]
      schedule?: Partial<ScheduleDraft>
      demands?: Partial<DemandRow>[]
      breakdowns?: Partial<BreakdownRow>[]
      // Plain `string` so tests/fixtures with object literals
      // (where 'mix-driven' widens to string) can pass through;
      // narrowed to SimulationMode at assignment.
      mode?: string
      total_demand?: number
      horizon_days?: number
    }): void {
      if (config.operations) {
        this.operations = config.operations.map((op, idx) => ({
          ...getDefaultOperation(),
          ...op,
          _id: Date.now() + idx,
        })) as OperationRow[]
      }
      if (config.schedule) {
        this.schedule = { ...getDefaultSchedule(), ...config.schedule } as ScheduleDraft
      }
      if (config.demands) {
        this.demands = config.demands.map((d, idx) => ({
          ...getDefaultDemand(),
          ...d,
          _id: Date.now() + idx,
        })) as DemandRow[]
      }
      if (config.breakdowns) {
        this.breakdowns = config.breakdowns.map((b, idx) => ({
          ...getDefaultBreakdown(),
          ...b,
          _id: Date.now() + idx,
        })) as BreakdownRow[]
      }
      if (config.mode === 'demand-driven' || config.mode === 'mix-driven') {
        this.mode = config.mode
      }
      if (config.total_demand) {
        this.totalDemand = config.total_demand
      }
      if (config.horizon_days) {
        this.horizonDays = config.horizon_days
      }
    },

    exportConfiguration() {
      return this.buildConfig()
    },

    loadSampleData(): void {
      const sampleData = getSampleTShirtData()
      this.loadConfiguration(sampleData)
      markAsVisited()
    },

    isFirstVisit(): boolean {
      return svIsFirstVisit()
    },

    resetToSample(): void {
      this.reset()
      this.loadSampleData()
    },

    clearFirstVisitFlag(): void {
      clearVisitedFlag()
    },
  },
})
