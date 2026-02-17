/**
 * Analysis Sub-Store
 *
 * Handles MRP / Component Check, Capacity Analysis, Schedule generation
 * and commitment, Scenario CRUD and comparison, and KPI integration.
 */

import { defineStore } from 'pinia'
import * as capacityApi from '@/services/api/capacityPlanning'
import { useWorksheetOpsStore } from './useWorksheetOps'
import { useWorkbookStore } from './useWorkbookStore'

export const useAnalysisStore = defineStore('capacityPlanning-analysis', {
  state: () => ({
    // MRP / Component Check
    mrpResults: null,
    isRunningMRP: false,
    mrpError: null,
    showMRPResultsDialog: false,

    // Scenario
    activeScenario: null,
    scenarioComparisonResults: null,
    isCreatingScenario: false,
    showScenarioCompareDialog: false,

    // Schedule
    activeSchedule: null,
    isGeneratingSchedule: false,
    isCommittingSchedule: false,
    showScheduleCommitDialog: false,

    // Analysis
    analysisResults: null,
    isRunningAnalysis: false
  }),

  actions: {
    // ---- MRP / Component Check ----

    async runComponentCheck(orderIds = null) {
      const wb = useWorkbookStore()
      const wsOps = useWorksheetOpsStore()
      if (!wb.clientId) return null

      this.isRunningMRP = true
      this.mrpError = null
      this.mrpResults = null

      try {
        const results = await capacityApi.runComponentCheck(wb.clientId, orderIds)
        this.mrpResults = results

        if (results.components) {
          wsOps.worksheets.componentCheck.data = results.components.map((c, idx) => ({
            ...c,
            _id: c.id || (Date.now() + idx)
          }))
        }

        this.showMRPResultsDialog = true
        return results
      } catch (error) {
        this.mrpError = error.message || 'Component check failed'
        throw error
      } finally {
        this.isRunningMRP = false
      }
    },

    clearMRPResults() {
      this.mrpResults = null
      this.mrpError = null
      this.showMRPResultsDialog = false
    },

    // ---- BOM Explosion ----

    async explodeBOM(parentItemCode, quantity) {
      const wb = useWorkbookStore()
      if (!wb.clientId) return null

      try {
        const result = await capacityApi.explodeBOM(wb.clientId, parentItemCode, quantity)
        return result
      } catch (error) {
        throw error
      }
    },

    // ---- Capacity Analysis ----

    async runCapacityAnalysis(startDate, endDate, lineIds = null) {
      const wb = useWorkbookStore()
      const wsOps = useWorksheetOpsStore()
      if (!wb.clientId) return null

      this.isRunningAnalysis = true

      try {
        const results = await capacityApi.runCapacityAnalysis(
          wb.clientId, startDate, endDate, lineIds
        )
        this.analysisResults = results

        if (results.line_results) {
          wsOps.worksheets.capacityAnalysis.data = results.line_results.map((r, idx) => ({
            ...r,
            _id: r.id || (Date.now() + idx)
          }))
        }

        return results
      } catch (error) {
        throw error
      } finally {
        this.isRunningAnalysis = false
      }
    },

    clearAnalysisResults() {
      this.analysisResults = null
    },

    // ---- Schedule Operations ----

    async generateSchedule(name, startDate, endDate, orderIds = null) {
      const wb = useWorkbookStore()
      const wsOps = useWorksheetOpsStore()
      if (!wb.clientId) return null

      this.isGeneratingSchedule = true

      try {
        const schedule = await capacityApi.generateSchedule(
          wb.clientId, name, startDate, endDate, orderIds
        )
        this.activeSchedule = schedule

        if (schedule.details) {
          wsOps.worksheets.productionSchedule.data = schedule.details.map((d, idx) => ({
            ...d,
            _id: d.id || (Date.now() + idx)
          }))
        }

        return schedule
      } catch (error) {
        throw error
      } finally {
        this.isGeneratingSchedule = false
      }
    },

    async commitSchedule(scheduleId, kpiCommitments) {
      const wb = useWorkbookStore()
      const wsOps = useWorksheetOpsStore()
      if (!wb.clientId) return null

      this.isCommittingSchedule = true
      this.showScheduleCommitDialog = false

      try {
        const result = await capacityApi.commitSchedule(scheduleId, kpiCommitments)

        if (result.kpi_commitments) {
          wsOps.worksheets.kpiTracking.data = result.kpi_commitments.map((k, idx) => ({
            ...k,
            _id: k.id || (Date.now() + idx)
          }))
        }

        if (this.activeSchedule && this.activeSchedule.id === scheduleId) {
          this.activeSchedule.status = 'COMMITTED'
        }

        return result
      } catch (error) {
        throw error
      } finally {
        this.isCommittingSchedule = false
      }
    },

    async loadSchedule(scheduleId) {
      const wb = useWorkbookStore()
      const wsOps = useWorksheetOpsStore()
      if (!wb.clientId) return null

      try {
        const schedule = await capacityApi.getSchedule(scheduleId)
        this.activeSchedule = schedule

        if (schedule.details) {
          wsOps.worksheets.productionSchedule.data = schedule.details.map((d, idx) => ({
            ...d,
            _id: d.id || (Date.now() + idx)
          }))
        }

        return schedule
      } catch (error) {
        throw error
      }
    },

    // ---- Scenario Operations ----

    async createScenario(name, type, parameters, baseScheduleId = null) {
      const wb = useWorkbookStore()
      const wsOps = useWorksheetOpsStore()
      if (!wb.clientId) return null

      this.isCreatingScenario = true

      try {
        const scenario = await capacityApi.createScenario(
          wb.clientId, name, type, parameters, baseScheduleId
        )

        wsOps.worksheets.whatIfScenarios.data.push({
          ...scenario,
          _id: scenario.id || Date.now()
        })
        wsOps.worksheets.whatIfScenarios.dirty = true

        this.activeScenario = scenario
        return scenario
      } catch (error) {
        throw error
      } finally {
        this.isCreatingScenario = false
      }
    },

    async runScenario(scenarioId) {
      const wb = useWorkbookStore()
      const wsOps = useWorksheetOpsStore()
      if (!wb.clientId) return null

      try {
        const results = await capacityApi.runScenario(wb.clientId, scenarioId)

        const idx = wsOps.worksheets.whatIfScenarios.data.findIndex(s => s.id === scenarioId)
        if (idx !== -1) {
          wsOps.worksheets.whatIfScenarios.data[idx] = {
            ...wsOps.worksheets.whatIfScenarios.data[idx],
            ...results,
            status: 'EVALUATED'
          }
        }

        return results
      } catch (error) {
        throw error
      }
    },

    async compareScenarios(scenarioIds) {
      const wb = useWorkbookStore()
      if (!wb.clientId) return null

      try {
        const results = await capacityApi.compareScenarios(wb.clientId, scenarioIds)
        this.scenarioComparisonResults = results
        this.showScenarioCompareDialog = true
        return results
      } catch (error) {
        throw error
      }
    },

    async deleteScenario(scenarioId) {
      const wb = useWorkbookStore()
      const wsOps = useWorksheetOpsStore()

      try {
        await capacityApi.deleteScenario(wb.clientId, scenarioId)

        const idx = wsOps.worksheets.whatIfScenarios.data.findIndex(s => s.id === scenarioId)
        if (idx !== -1) {
          wsOps.worksheets.whatIfScenarios.data.splice(idx, 1)
        }

        if (this.activeScenario?.id === scenarioId) {
          this.activeScenario = null
        }

        return true
      } catch (error) {
        throw error
      }
    },

    // ---- Reset ----

    resetAnalysis() {
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
    }
  }
})
