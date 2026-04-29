/**
 * Analysis sub-store — MRP/component check, capacity analysis,
 * schedule generation/commit, scenario CRUD/comparison.
 */

import { defineStore } from 'pinia'
import * as capacityApi from '@/services/api/capacityPlanning'
import { useWorksheetOpsStore, type WorksheetRow } from './useWorksheetOps'
import { useWorkbookStore } from './useWorkbookStore'

export interface MRPResults {
  components?: WorksheetRow[]
  [key: string]: unknown
}

export interface CapacityAnalysisResults {
  line_results?: WorksheetRow[]
  [key: string]: unknown
}

export interface ScheduleResult {
  id?: string | number
  status?: string
  details?: WorksheetRow[]
  [key: string]: unknown
}

export interface CommitResult {
  kpi_commitments?: WorksheetRow[]
  [key: string]: unknown
}

export interface ScenarioResult {
  id?: string | number
  [key: string]: unknown
}

interface AnalysisState {
  mrpResults: MRPResults | null
  isRunningMRP: boolean
  mrpError: string | null
  showMRPResultsDialog: boolean
  activeScenario: ScenarioResult | null
  scenarioComparisonResults: unknown | null
  isCreatingScenario: boolean
  showScenarioCompareDialog: boolean
  activeSchedule: ScheduleResult | null
  isGeneratingSchedule: boolean
  isCommittingSchedule: boolean
  showScheduleCommitDialog: boolean
  analysisResults: CapacityAnalysisResults | null
  isRunningAnalysis: boolean
}

const errMessage = (e: unknown, fallback: string): string =>
  e instanceof Error ? e.message : fallback

const withId = (idx: number) => (row: WorksheetRow): WorksheetRow => ({
  ...row,
  _id: row.id || Date.now() + idx,
})

export const useAnalysisStore = defineStore('capacityPlanning-analysis', {
  state: (): AnalysisState => ({
    mrpResults: null,
    isRunningMRP: false,
    mrpError: null,
    showMRPResultsDialog: false,
    activeScenario: null,
    scenarioComparisonResults: null,
    isCreatingScenario: false,
    showScenarioCompareDialog: false,
    activeSchedule: null,
    isGeneratingSchedule: false,
    isCommittingSchedule: false,
    showScheduleCommitDialog: false,
    analysisResults: null,
    isRunningAnalysis: false,
  }),

  actions: {
    async runComponentCheck(
      orderIds: (string | number)[] | null = null,
    ): Promise<MRPResults | null> {
      const wb = useWorkbookStore()
      const wsOps = useWorksheetOpsStore()
      if (!wb.clientId) return null

      this.isRunningMRP = true
      this.mrpError = null
      this.mrpResults = null

      try {
        const results = (await capacityApi.runComponentCheck(
          wb.clientId as number,
          orderIds as number[],
        )) as MRPResults
        this.mrpResults = results

        if (results.components) {
          wsOps.worksheets.componentCheck.data = results.components.map((c, i) => withId(i)(c))
        }

        this.showMRPResultsDialog = true
        return results
      } catch (error) {
        this.mrpError = errMessage(error, 'Component check failed')
        throw error
      } finally {
        this.isRunningMRP = false
      }
    },

    clearMRPResults(): void {
      this.mrpResults = null
      this.mrpError = null
      this.showMRPResultsDialog = false
    },

    async explodeBOM(parentItemCode: string, quantity: number): Promise<unknown> {
      const wb = useWorkbookStore()
      if (!wb.clientId) return null

      return await capacityApi.explodeBOM(wb.clientId as number, parentItemCode, quantity)
    },

    async runCapacityAnalysis(
      startDate: string,
      endDate: string,
      lineIds: (string | number)[] | null = null,
    ): Promise<CapacityAnalysisResults | null> {
      const wb = useWorkbookStore()
      const wsOps = useWorksheetOpsStore()
      if (!wb.clientId) return null

      this.isRunningAnalysis = true

      try {
        const results = (await capacityApi.runCapacityAnalysis(
          wb.clientId as number,
          startDate,
          endDate,
          lineIds as number[],
        )) as CapacityAnalysisResults
        this.analysisResults = results

        if (results.line_results) {
          wsOps.worksheets.capacityAnalysis.data = results.line_results.map((r, i) =>
            withId(i)(r),
          )
        }

        return results
      } finally {
        this.isRunningAnalysis = false
      }
    },

    clearAnalysisResults(): void {
      this.analysisResults = null
    },

    async generateSchedule(
      name: string,
      startDate: string,
      endDate: string,
      orderIds: (string | number)[] | null = null,
    ): Promise<ScheduleResult | null> {
      const wb = useWorkbookStore()
      const wsOps = useWorksheetOpsStore()
      if (!wb.clientId) return null

      this.isGeneratingSchedule = true

      try {
        const schedule = (await capacityApi.generateSchedule(
          wb.clientId as number,
          name,
          startDate,
          endDate,
          orderIds as number[],
        )) as ScheduleResult
        this.activeSchedule = schedule

        if (schedule.details) {
          wsOps.worksheets.productionSchedule.data = schedule.details.map((d, i) =>
            withId(i)(d),
          )
        }

        return schedule
      } finally {
        this.isGeneratingSchedule = false
      }
    },

    async commitSchedule(
      scheduleId: string | number,
      kpiCommitments: Record<string, unknown>,
    ): Promise<CommitResult | null> {
      const wb = useWorkbookStore()
      const wsOps = useWorksheetOpsStore()
      if (!wb.clientId) return null

      this.isCommittingSchedule = true
      this.showScheduleCommitDialog = false

      try {
        const result = (await capacityApi.commitSchedule(
          scheduleId as number,
          kpiCommitments,
        )) as CommitResult

        if (result.kpi_commitments) {
          wsOps.worksheets.kpiTracking.data = result.kpi_commitments.map((k, i) =>
            withId(i)(k),
          )
        }

        if (this.activeSchedule && this.activeSchedule.id === scheduleId) {
          this.activeSchedule.status = 'COMMITTED'
        }

        return result
      } finally {
        this.isCommittingSchedule = false
      }
    },

    async loadSchedule(scheduleId: string | number): Promise<ScheduleResult | null> {
      const wb = useWorkbookStore()
      const wsOps = useWorksheetOpsStore()
      if (!wb.clientId) return null

      const schedule = (await capacityApi.getSchedule(
        wb.clientId as number,
        scheduleId as number,
      )) as ScheduleResult
      this.activeSchedule = schedule

      if (schedule.details) {
        wsOps.worksheets.productionSchedule.data = schedule.details.map((d, i) =>
          withId(i)(d),
        )
      }

      return schedule
    },

    async createScenario(
      name: string,
      type: string,
      parameters: Record<string, unknown>,
      baseScheduleId: string | number | null = null,
    ): Promise<ScenarioResult | null> {
      const wb = useWorkbookStore()
      const wsOps = useWorksheetOpsStore()
      if (!wb.clientId) return null

      this.isCreatingScenario = true

      try {
        const scenario = (await capacityApi.createScenario(
          wb.clientId as number,
          name,
          type,
          parameters,
          baseScheduleId as number | null,
        )) as ScenarioResult

        wsOps.worksheets.whatIfScenarios.data.push({
          ...scenario,
          _id: scenario.id || Date.now(),
        })
        wsOps.worksheets.whatIfScenarios.dirty = true

        this.activeScenario = scenario
        return scenario
      } finally {
        this.isCreatingScenario = false
      }
    },

    async runScenario(scenarioId: string | number): Promise<unknown | null> {
      const wb = useWorkbookStore()
      const wsOps = useWorksheetOpsStore()
      if (!wb.clientId) return null

      const results = (await capacityApi.runScenario(
        wb.clientId as number,
        scenarioId as number,
      )) as Record<string, unknown>

      const idx = wsOps.worksheets.whatIfScenarios.data.findIndex((s) => s.id === scenarioId)
      if (idx !== -1) {
        wsOps.worksheets.whatIfScenarios.data[idx] = {
          ...wsOps.worksheets.whatIfScenarios.data[idx],
          ...results,
          status: 'EVALUATED',
        }
      }

      return results
    },

    async compareScenarios(scenarioIds: (string | number)[]): Promise<unknown | null> {
      const wb = useWorkbookStore()
      if (!wb.clientId) return null

      const results = await capacityApi.compareScenarios(
        wb.clientId as number,
        scenarioIds as number[],
      )
      this.scenarioComparisonResults = results
      this.showScenarioCompareDialog = true
      return results
    },

    async deleteScenario(scenarioId: string | number): Promise<boolean> {
      const wb = useWorkbookStore()
      const wsOps = useWorksheetOpsStore()

      await capacityApi.deleteScenario(wb.clientId as number, scenarioId as number)

      const idx = wsOps.worksheets.whatIfScenarios.data.findIndex((s) => s.id === scenarioId)
      if (idx !== -1) {
        wsOps.worksheets.whatIfScenarios.data.splice(idx, 1)
      }

      if (this.activeScenario?.id === scenarioId) {
        this.activeScenario = null
      }

      return true
    },

    resetAnalysis(): void {
      this.mrpResults = null
      this.mrpError = null
      this.showMRPResultsDialog = false
      this.analysisResults = null
      this.activeScenario = null
      this.scenarioComparisonResults = null
      this.showScenarioCompareDialog = false
      this.activeSchedule = null
      this.showScheduleCommitDialog = false
      this.isRunningMRP = false
      this.isRunningAnalysis = false
      this.isGeneratingSchedule = false
      this.isCommittingSchedule = false
      this.isCreatingScenario = false
    },
  },
})
