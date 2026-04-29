/**
 * Workbook sub-store — load/save (single worksheet, all dirty,
 * full workbook) and discard. Backed by the worksheet ops sub-
 * store for the row data.
 */

import { defineStore } from 'pinia'
import * as capacityApi from '@/services/api/capacityPlanning'
import { useWorksheetOpsStore, type WorksheetRow } from './useWorksheetOps'
import { getDefaultDashboardInputs, type DashboardInputs } from './defaults'

interface WorkbookState {
  clientId: string | number | null
  isLoading: boolean
  isSaving: boolean
  globalError: string | null
  lastSaved: Date | null
}

interface SaveAllResults {
  success: string[]
  failed: { name: string; error: string }[]
}

const WORKSHEET_MAPPING: Record<string, string> = {
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
  instructions: 'instructions',
}

const errMessage = (e: unknown, fallback: string): string =>
  e instanceof Error ? e.message : fallback

export const useWorkbookStore = defineStore('capacityPlanning-workbook', {
  state: (): WorkbookState => ({
    clientId: null,
    isLoading: false,
    isSaving: false,
    globalError: null,
    lastSaved: null,
  }),

  actions: {
    setClientId(clientId: string | number | null): void {
      this.clientId = clientId
    },

    async loadWorkbook(clientId: string | number | null = null): Promise<unknown> {
      const wsOps = useWorksheetOpsStore()
      const targetClientId = clientId || this.clientId
      if (!targetClientId) {
        throw new Error('Client ID is required')
      }

      this.clientId = targetClientId
      this.isLoading = true
      this.globalError = null

      try {
        const workbook = (await capacityApi.loadWorkbook(
          targetClientId as number,
        )) as Record<string, unknown>

        for (const [storeKey, apiKey] of Object.entries(WORKSHEET_MAPPING)) {
          if (workbook[apiKey] !== undefined) {
            const apiData = workbook[apiKey]
            if (storeKey === 'instructions') {
              ;(wsOps.worksheets.instructions as { content: string }).content =
                apiData as string
            } else if (storeKey === 'dashboardInputs') {
              wsOps.worksheets.dashboardInputs.data = {
                ...getDefaultDashboardInputs(),
                ...(apiData as Partial<DashboardInputs>),
              }
            } else {
              const ws = (wsOps.worksheets as unknown as Record<string, { data: WorksheetRow[] }>)[
                storeKey
              ]
              ws.data = (apiData as WorksheetRow[]).map((row, idx) => ({
                ...row,
                _id: row.id || Date.now() + idx,
              }))
            }
          }
        }

        Object.values(wsOps.worksheets).forEach((ws) => {
          ws.dirty = false
          ws.error = null
        })

        wsOps.initHistory()
        wsOps._historyManager?.clear()

        return workbook
      } catch (error) {
        this.globalError = errMessage(error, 'Failed to load workbook')
        throw error
      } finally {
        this.isLoading = false
      }
    },

    async saveWorksheet(worksheetName: string): Promise<boolean> {
      const wsOps = useWorksheetOpsStore()
      const worksheet = (
        wsOps.worksheets as unknown as Record<
          string,
          { data?: unknown; content?: string; loading: boolean; error: string | null; dirty: boolean }
        >
      )[worksheetName]
      if (!worksheet || !this.clientId) return false

      worksheet.loading = true
      worksheet.error = null

      try {
        const dataToSave =
          worksheetName === 'instructions'
            ? (worksheet as { content: string }).content
            : (worksheet as { data: unknown }).data

        await capacityApi.saveWorksheet(
          worksheetName,
          this.clientId as number,
          dataToSave as Record<string, unknown>,
        )
        worksheet.dirty = false
        this.lastSaved = new Date()

        const wsAny = worksheet as { data?: unknown }
        if (Array.isArray(wsAny.data)) {
          ;(wsAny.data as WorksheetRow[]).forEach((row) => {
            delete row._isNew
            delete row._imported
          })
        }

        return true
      } catch (error) {
        worksheet.error = errMessage(error, 'Failed to save')
        throw error
      } finally {
        worksheet.loading = false
      }
    },

    async saveAllDirty(): Promise<SaveAllResults> {
      const wsOps = useWorksheetOpsStore()
      this.isSaving = true
      const results: SaveAllResults = { success: [], failed: [] }

      for (const [name, worksheet] of Object.entries(wsOps.worksheets)) {
        if (worksheet.dirty) {
          try {
            await this.saveWorksheet(name)
            results.success.push(name)
          } catch (error) {
            results.failed.push({ name, error: errMessage(error, 'Save failed') })
          }
        }
      }

      this.isSaving = false
      return results
    },

    async saveWorkbook(): Promise<boolean> {
      const wsOps = useWorksheetOpsStore()
      if (!this.clientId) return false

      this.isSaving = true
      this.globalError = null

      try {
        const workbookData: Record<string, unknown> = {}

        for (const [key, worksheet] of Object.entries(wsOps.worksheets)) {
          if (key === 'instructions') {
            workbookData[key] = (worksheet as { content: string }).content
          } else {
            workbookData[key] = (worksheet as { data: unknown }).data
          }
        }

        await capacityApi.saveWorkbook(
          this.clientId as number,
          workbookData as Record<string, Record<string, unknown>>,
        )

        Object.values(wsOps.worksheets).forEach((ws) => {
          ws.dirty = false
        })

        this.lastSaved = new Date()
        return true
      } catch (error) {
        this.globalError = errMessage(error, 'Failed to save workbook')
        throw error
      } finally {
        this.isSaving = false
      }
    },

    async discardChanges(): Promise<boolean> {
      if (!this.clientId) return false

      await this.loadWorkbook(this.clientId)
      return true
    },
  },
})
