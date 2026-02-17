/**
 * Workbook Sub-Store
 *
 * Handles workbook-level operations: load, save (single worksheet, all dirty,
 * full workbook), and discard changes. Works with the worksheet ops store
 * for data access.
 */

import { defineStore } from 'pinia'
import * as capacityApi from '@/services/api/capacityPlanning'
import { useWorksheetOpsStore } from './useWorksheetOps'
import { getDefaultDashboardInputs } from './defaults'

export const useWorkbookStore = defineStore('capacityPlanning-workbook', {
  state: () => ({
    clientId: null,
    isLoading: false,
    isSaving: false,
    globalError: null,
    lastSaved: null
  }),

  actions: {
    setClientId(clientId) {
      this.clientId = clientId
    },

    async loadWorkbook(clientId = null) {
      const wsOps = useWorksheetOpsStore()
      const targetClientId = clientId || this.clientId
      if (!targetClientId) {
        throw new Error('Client ID is required')
      }

      this.clientId = targetClientId
      this.isLoading = true
      this.globalError = null

      try {
        const workbook = await capacityApi.loadWorkbook(targetClientId)

        const worksheetMapping = {
          masterCalendar: 'master_calendar',
          productionLines: 'production_lines',
          orders: 'orders',
          productionStandards: 'production_standards',
          bom: 'bom',
          stockSnapshot: 'stock_snapshot',
          componentCheck: 'component_check',
          capacityAnalysis: 'capacity_analysis',
          productionSchedule: 'production_schedule',
          whatIfScenarios: 'what_if_scenarios',
          dashboardInputs: 'dashboard_inputs',
          kpiTracking: 'kpi_tracking',
          instructions: 'instructions'
        }

        for (const [storeKey, apiKey] of Object.entries(worksheetMapping)) {
          if (workbook[apiKey]) {
            if (storeKey === 'instructions') {
              wsOps.worksheets[storeKey].content = workbook[apiKey]
            } else if (storeKey === 'dashboardInputs') {
              wsOps.worksheets[storeKey].data = { ...getDefaultDashboardInputs(), ...workbook[apiKey] }
            } else {
              wsOps.worksheets[storeKey].data = workbook[apiKey].map((row, idx) => ({
                ...row,
                _id: row.id || (Date.now() + idx)
              }))
            }
          }
        }

        // Reset dirty flags and errors
        Object.values(wsOps.worksheets).forEach(ws => {
          ws.dirty = false
          ws.error = null
        })

        // Initialize history
        wsOps.initHistory()
        wsOps._historyManager.clear()

        return workbook
      } catch (error) {
        this.globalError = error.message || 'Failed to load workbook'
        throw error
      } finally {
        this.isLoading = false
      }
    },

    async saveWorksheet(worksheetName) {
      const wsOps = useWorksheetOpsStore()
      const worksheet = wsOps.worksheets[worksheetName]
      if (!worksheet || !this.clientId) return false

      worksheet.loading = true
      worksheet.error = null

      try {
        const dataToSave = worksheetName === 'instructions'
          ? worksheet.content
          : worksheet.data

        await capacityApi.saveWorksheet(worksheetName, this.clientId, dataToSave)
        worksheet.dirty = false
        this.lastSaved = new Date()

        // Clear _isNew flags
        if (Array.isArray(worksheet.data)) {
          worksheet.data.forEach(row => {
            delete row._isNew
            delete row._imported
          })
        }

        return true
      } catch (error) {
        worksheet.error = error.message || 'Failed to save'
        throw error
      } finally {
        worksheet.loading = false
      }
    },

    async saveAllDirty() {
      const wsOps = useWorksheetOpsStore()
      this.isSaving = true
      const results = { success: [], failed: [] }

      for (const [name, worksheet] of Object.entries(wsOps.worksheets)) {
        if (worksheet.dirty) {
          try {
            await this.saveWorksheet(name)
            results.success.push(name)
          } catch (error) {
            results.failed.push({ name, error: error.message })
          }
        }
      }

      this.isSaving = false
      return results
    },

    async saveWorkbook() {
      const wsOps = useWorksheetOpsStore()
      if (!this.clientId) return false

      this.isSaving = true
      this.globalError = null

      try {
        const workbookData = {}

        for (const [key, worksheet] of Object.entries(wsOps.worksheets)) {
          if (key === 'instructions') {
            workbookData[key] = worksheet.content
          } else {
            workbookData[key] = worksheet.data
          }
        }

        await capacityApi.saveWorkbook(this.clientId, workbookData)

        // Reset all dirty flags
        Object.values(wsOps.worksheets).forEach(ws => {
          ws.dirty = false
        })

        this.lastSaved = new Date()
        return true
      } catch (error) {
        this.globalError = error.message || 'Failed to save workbook'
        throw error
      } finally {
        this.isSaving = false
      }
    },

    async discardChanges() {
      if (!this.clientId) return false

      await this.loadWorkbook(this.clientId)
      return true
    }
  }
})
