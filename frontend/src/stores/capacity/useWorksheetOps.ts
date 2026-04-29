/**
 * Worksheet operations sub-store — generic CRUD row ops (add, update,
 * remove, duplicate, insert, import, append) plus undo/redo across
 * the 13 capacity-planning worksheets.
 */

import { defineStore } from 'pinia'
import { createHistoryManager, HistoryManager } from './historyManager'
import {
  getDefaultBOMDetail,
  getDefaultDashboardInputs,
  defaultFactoryMap,
  DashboardInputs,
} from './defaults'

export interface WorksheetRow {
  _id?: number | string
  _isNew?: boolean
  _imported?: boolean
  id?: number | string
  [key: string]: unknown
}

export interface DataWorksheet {
  data: WorksheetRow[]
  dirty: boolean
  loading: boolean
  error: string | null
}

export interface DashboardInputsWorksheet {
  data: DashboardInputs
  dirty: boolean
  loading: boolean
  error: string | null
}

export interface InstructionsWorksheet {
  content: string
  dirty: boolean
  loading: boolean
  error: string | null
}

export interface Worksheets {
  masterCalendar: DataWorksheet
  productionLines: DataWorksheet
  orders: DataWorksheet
  productionStandards: DataWorksheet
  bom: DataWorksheet
  stockSnapshot: DataWorksheet
  componentCheck: DataWorksheet
  capacityAnalysis: DataWorksheet
  productionSchedule: DataWorksheet
  whatIfScenarios: DataWorksheet
  dashboardInputs: DashboardInputsWorksheet
  kpiTracking: DataWorksheet
  instructions: InstructionsWorksheet
}

// Union of all worksheet variants — used inside the actions for
// dynamic-key access (e.g. `worksheets[worksheetName]`).
type AnyWorksheet = DataWorksheet | DashboardInputsWorksheet | InstructionsWorksheet

export type WorksheetName = keyof Worksheets

interface WorksheetOpsState {
  worksheets: Worksheets
  _historyManager: HistoryManager<unknown> | null
}

const makeDataWs = (): DataWorksheet => ({
  data: [],
  dirty: false,
  loading: false,
  error: null,
})

const makeDashboardInputsWs = (): DashboardInputsWorksheet => ({
  data: getDefaultDashboardInputs(),
  dirty: false,
  loading: false,
  error: null,
})

const makeInstructionsWs = (): InstructionsWorksheet => ({
  content: '',
  dirty: false,
  loading: false,
  error: null,
})

const isDataWs = (ws: unknown): ws is DataWorksheet =>
  typeof ws === 'object' && ws !== null && Array.isArray((ws as DataWorksheet).data)

export const useWorksheetOpsStore = defineStore('capacityPlanning-worksheetOps', {
  state: (): WorksheetOpsState => ({
    worksheets: {
      masterCalendar: makeDataWs(),
      productionLines: makeDataWs(),
      orders: makeDataWs(),
      productionStandards: makeDataWs(),
      bom: makeDataWs(),
      stockSnapshot: makeDataWs(),
      componentCheck: makeDataWs(),
      capacityAnalysis: makeDataWs(),
      productionSchedule: makeDataWs(),
      whatIfScenarios: makeDataWs(),
      dashboardInputs: makeDashboardInputsWs(),
      kpiTracking: makeDataWs(),
      instructions: makeInstructionsWs(),
    },
    _historyManager: null,
  }),

  getters: {
    hasUnsavedChanges: (state): boolean =>
      Object.values(state.worksheets).some((ws) => ws.dirty),

    dirtyWorksheets: (state): string[] =>
      Object.entries(state.worksheets)
        .filter(([, ws]) => ws.dirty)
        .map(([name]) => name),

    dirtyCount: (state): number =>
      Object.values(state.worksheets).filter((ws) => ws.dirty).length,

    canUndo: (state): boolean => state._historyManager?.canUndo() || false,

    canRedo: (state): boolean => state._historyManager?.canRedo() || false,
  },

  actions: {
    initHistory(): void {
      if (!this._historyManager) {
        this._historyManager = createHistoryManager(50)
      }
    },

    _saveToHistory(worksheetName: string): void {
      if (!this._historyManager) {
        this.initHistory()
      }
      const worksheet = (this.worksheets as Record<string, AnyWorksheet>)[worksheetName]
      if (worksheet && isDataWs(worksheet)) {
        this._historyManager?.push({
          worksheetName,
          data: JSON.parse(JSON.stringify(worksheet.data)),
        })
      }
    },

    undo(): boolean {
      if (!this._historyManager?.canUndo()) return false

      const previousState = this._historyManager.undo()
      if (previousState && previousState.worksheetName) {
        const worksheet = (this.worksheets as Record<string, AnyWorksheet>)[previousState.worksheetName]
        if (worksheet && isDataWs(worksheet)) {
          worksheet.data = previousState.data as WorksheetRow[]
          worksheet.dirty = true
        }
      }

      return true
    },

    redo(): boolean {
      if (!this._historyManager?.canRedo()) return false

      const nextState = this._historyManager.redo()
      if (nextState && nextState.worksheetName) {
        const worksheet = (this.worksheets as Record<string, AnyWorksheet>)[nextState.worksheetName]
        if (worksheet && isDataWs(worksheet)) {
          worksheet.data = nextState.data as WorksheetRow[]
          worksheet.dirty = true
        }
      }

      return true
    },

    updateCell(
      worksheetName: string,
      rowIndex: number,
      field: string,
      value: unknown,
    ): void {
      const worksheet = (this.worksheets as Record<string, AnyWorksheet>)[worksheetName]
      if (!worksheet || !isDataWs(worksheet) || !worksheet.data[rowIndex]) return

      this._saveToHistory(worksheetName)
      worksheet.data[rowIndex][field] = value
      worksheet.dirty = true
    },

    updateRow(
      worksheetName: string,
      rowIndex: number,
      updates: Partial<WorksheetRow>,
    ): void {
      const worksheet = (this.worksheets as Record<string, AnyWorksheet>)[worksheetName]
      if (!worksheet || !isDataWs(worksheet) || !worksheet.data[rowIndex]) return

      this._saveToHistory(worksheetName)
      Object.assign(worksheet.data[rowIndex], updates)
      worksheet.dirty = true
    },

    addRow(worksheetName: string): WorksheetRow | null {
      const worksheet = (this.worksheets as Record<string, AnyWorksheet>)[worksheetName]
      if (!worksheet || !isDataWs(worksheet)) return null

      this._saveToHistory(worksheetName)

      const factory = defaultFactoryMap[worksheetName]
      const newRow: WorksheetRow = factory ? factory() : {}

      newRow._id = Date.now()
      newRow._isNew = true
      worksheet.data.push(newRow)
      worksheet.dirty = true

      return newRow
    },

    insertRow(
      worksheetName: string,
      index: number,
      row: WorksheetRow | null = null,
    ): WorksheetRow | null {
      const worksheet = (this.worksheets as Record<string, AnyWorksheet>)[worksheetName]
      if (!worksheet || !isDataWs(worksheet)) return null

      this._saveToHistory(worksheetName)

      const newRow = row || this.addRow(worksheetName)
      if (newRow && index >= 0 && index < worksheet.data.length) {
        worksheet.data.pop()
        worksheet.data.splice(index, 0, newRow)
      }

      return newRow
    },

    removeRow(worksheetName: string, rowIndex: number): boolean {
      const worksheet = (this.worksheets as Record<string, AnyWorksheet>)[worksheetName]
      if (
        !worksheet ||
        !isDataWs(worksheet) ||
        rowIndex < 0 ||
        rowIndex >= worksheet.data.length
      ) {
        return false
      }

      this._saveToHistory(worksheetName)
      worksheet.data.splice(rowIndex, 1)
      worksheet.dirty = true

      return true
    },

    removeRows(worksheetName: string, indices: number[]): boolean {
      const worksheet = (this.worksheets as Record<string, AnyWorksheet>)[worksheetName]
      if (!worksheet || !isDataWs(worksheet)) return false

      this._saveToHistory(worksheetName)

      const sortedIndices = [...indices].sort((a, b) => b - a)
      for (const idx of sortedIndices) {
        if (idx >= 0 && idx < worksheet.data.length) {
          worksheet.data.splice(idx, 1)
        }
      }

      worksheet.dirty = true
      return true
    },

    duplicateRow(worksheetName: string, rowIndex: number): WorksheetRow | null {
      const worksheet = (this.worksheets as Record<string, AnyWorksheet>)[worksheetName]
      if (
        !worksheet ||
        !isDataWs(worksheet) ||
        rowIndex < 0 ||
        rowIndex >= worksheet.data.length
      ) {
        return null
      }

      this._saveToHistory(worksheetName)

      const original = worksheet.data[rowIndex]
      const duplicate: WorksheetRow = {
        ...JSON.parse(JSON.stringify(original)),
        _id: Date.now(),
        _isNew: true,
      }

      delete duplicate.id
      if (typeof duplicate.order_number === 'string') {
        duplicate.order_number = `${duplicate.order_number}-COPY`
      }
      if (typeof duplicate.line_code === 'string') {
        duplicate.line_code = `${duplicate.line_code}-COPY`
      }

      worksheet.data.splice(rowIndex + 1, 0, duplicate)
      worksheet.dirty = true

      return duplicate
    },

    importData(worksheetName: string, data: WorksheetRow[]): boolean {
      const worksheet = (this.worksheets as Record<string, AnyWorksheet>)[worksheetName]
      if (!worksheet || !isDataWs(worksheet)) return false

      this._saveToHistory(worksheetName)

      worksheet.data = data.map((row, idx) => ({
        ...row,
        _id: row.id || Date.now() + idx,
        _imported: true,
      }))
      worksheet.dirty = true

      return true
    },

    appendData(worksheetName: string, data: WorksheetRow[]): boolean {
      const worksheet = (this.worksheets as Record<string, AnyWorksheet>)[worksheetName]
      if (!worksheet || !isDataWs(worksheet)) return false

      this._saveToHistory(worksheetName)

      const newRows: WorksheetRow[] = data.map((row, idx) => ({
        ...row,
        _id: row.id || Date.now() + idx,
        _imported: true,
      }))

      worksheet.data = [...worksheet.data, ...newRows]
      worksheet.dirty = true

      return true
    },

    updateDashboardInput(key: string, value: unknown): void {
      this._saveToHistory('dashboardInputs')
      ;(this.worksheets.dashboardInputs.data as Record<string, unknown>)[key] = value
      this.worksheets.dashboardInputs.dirty = true
    },

    exportWorksheetJSON(worksheetName: string): string | null {
      const worksheet = (this.worksheets as Record<string, AnyWorksheet>)[worksheetName]
      if (!worksheet) return null

      const data =
        worksheetName === 'instructions'
          ? (worksheet as InstructionsWorksheet).content
          : (worksheet as DataWorksheet | DashboardInputsWorksheet).data

      const cleanData = Array.isArray(data)
        ? data.map((row) => {
            const { _id, _isNew, _imported, ...clean } = row as WorksheetRow
            void _id
            void _isNew
            void _imported
            return clean
          })
        : data

      return JSON.stringify(cleanData, null, 2)
    },

    exportWorkbookJSON(): string {
      const workbook: Record<string, unknown> = {}

      for (const [key, worksheet] of Object.entries(this.worksheets)) {
        if (key === 'instructions') {
          workbook[key] = (worksheet as InstructionsWorksheet).content
        } else {
          const wsData = (worksheet as DataWorksheet | DashboardInputsWorksheet).data
          workbook[key] = Array.isArray(wsData)
            ? wsData.map((row) => {
                const { _id, _isNew, _imported, ...clean } = row as WorksheetRow
                void _id
                void _isNew
                void _imported
                return clean
              })
            : wsData
        }
      }

      return JSON.stringify(workbook, null, 2)
    },

    addBOMComponent(bomIndex: number): WorksheetRow | null {
      const bom = this.worksheets.bom.data[bomIndex]
      if (!bom) return null

      this._saveToHistory('bom')

      if (!Array.isArray(bom.components)) {
        bom.components = []
      }

      const newComponent: WorksheetRow = {
        ...getDefaultBOMDetail(),
        _id: Date.now(),
      }

      ;(bom.components as WorksheetRow[]).push(newComponent)
      this.worksheets.bom.dirty = true

      return newComponent
    },

    removeBOMComponent(bomIndex: number, componentIndex: number): boolean {
      const bom = this.worksheets.bom.data[bomIndex]
      if (!bom || !Array.isArray(bom.components) || componentIndex < 0) return false

      this._saveToHistory('bom')
      ;(bom.components as WorksheetRow[]).splice(componentIndex, 1)
      this.worksheets.bom.dirty = true

      return true
    },

    resetWorksheets(): void {
      Object.keys(this.worksheets).forEach((key) => {
        if (key === 'instructions') {
          (this.worksheets as Record<string, AnyWorksheet>)[key] = makeInstructionsWs()
        } else if (key === 'dashboardInputs') {
          (this.worksheets as Record<string, AnyWorksheet>)[key] = makeDashboardInputsWs()
        } else {
          (this.worksheets as Record<string, AnyWorksheet>)[key] = makeDataWs()
        }
      })

      if (this._historyManager) {
        this._historyManager.clear()
      }
    },

    clearAllErrors(): void {
      Object.values(this.worksheets).forEach((ws) => {
        ws.error = null
      })
    },
  },
})
