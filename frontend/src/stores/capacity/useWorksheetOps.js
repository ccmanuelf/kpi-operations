/**
 * Worksheet Operations Sub-Store
 *
 * Handles generic CRUD row operations (add, update, remove, duplicate,
 * insert, import, append) and undo/redo across all 13 worksheets.
 * Also manages the worksheet data structures, dirty tracking, and
 * history management.
 */

import { defineStore } from 'pinia'
import { createHistoryManager } from './historyManager'
import {
  getDefaultBOMDetail,
  getDefaultDashboardInputs,
  defaultFactoryMap
} from './defaults'

export const useWorksheetOpsStore = defineStore('capacityPlanning-worksheetOps', {
  state: () => ({
    // 13 worksheets with dirty tracking
    worksheets: {
      masterCalendar: { data: [], dirty: false, loading: false, error: null },
      productionLines: { data: [], dirty: false, loading: false, error: null },
      orders: { data: [], dirty: false, loading: false, error: null },
      productionStandards: { data: [], dirty: false, loading: false, error: null },
      bom: { data: [], dirty: false, loading: false, error: null },
      stockSnapshot: { data: [], dirty: false, loading: false, error: null },
      componentCheck: { data: [], dirty: false, loading: false, error: null },
      capacityAnalysis: { data: [], dirty: false, loading: false, error: null },
      productionSchedule: { data: [], dirty: false, loading: false, error: null },
      whatIfScenarios: { data: [], dirty: false, loading: false, error: null },
      dashboardInputs: { data: getDefaultDashboardInputs(), dirty: false, loading: false, error: null },
      kpiTracking: { data: [], dirty: false, loading: false, error: null },
      instructions: { content: '', dirty: false, loading: false, error: null }
    },

    // History for undo/redo (managed externally)
    _historyManager: null
  }),

  getters: {
    hasUnsavedChanges: (state) => {
      return Object.values(state.worksheets).some(ws => ws.dirty)
    },

    dirtyWorksheets: (state) => {
      return Object.entries(state.worksheets)
        .filter(([, ws]) => ws.dirty)
        .map(([name]) => name)
    },

    dirtyCount: (state) => {
      return Object.values(state.worksheets).filter(ws => ws.dirty).length
    },

    canUndo: (state) => {
      return state._historyManager?.canUndo() || false
    },

    canRedo: (state) => {
      return state._historyManager?.canRedo() || false
    }
  },

  actions: {
    // ---- History ----

    initHistory() {
      if (!this._historyManager) {
        this._historyManager = createHistoryManager(50)
      }
    },

    _saveToHistory(worksheetName) {
      if (!this._historyManager) {
        this.initHistory()
      }
      const worksheet = this.worksheets[worksheetName]
      if (worksheet) {
        this._historyManager.push({
          worksheetName,
          data: JSON.parse(JSON.stringify(worksheet.data))
        })
      }
    },

    undo() {
      if (!this._historyManager?.canUndo()) return false

      const previousState = this._historyManager.undo()
      if (previousState && previousState.worksheetName) {
        const worksheet = this.worksheets[previousState.worksheetName]
        if (worksheet) {
          worksheet.data = previousState.data
          worksheet.dirty = true
        }
      }

      return true
    },

    redo() {
      if (!this._historyManager?.canRedo()) return false

      const nextState = this._historyManager.redo()
      if (nextState && nextState.worksheetName) {
        const worksheet = this.worksheets[nextState.worksheetName]
        if (worksheet) {
          worksheet.data = nextState.data
          worksheet.dirty = true
        }
      }

      return true
    },

    // ---- Cell / Row Operations ----

    updateCell(worksheetName, rowIndex, field, value) {
      const worksheet = this.worksheets[worksheetName]
      if (!worksheet || !worksheet.data[rowIndex]) return

      this._saveToHistory(worksheetName)
      worksheet.data[rowIndex][field] = value
      worksheet.dirty = true
    },

    updateRow(worksheetName, rowIndex, updates) {
      const worksheet = this.worksheets[worksheetName]
      if (!worksheet || !worksheet.data[rowIndex]) return

      this._saveToHistory(worksheetName)
      Object.assign(worksheet.data[rowIndex], updates)
      worksheet.dirty = true
    },

    addRow(worksheetName) {
      const worksheet = this.worksheets[worksheetName]
      if (!worksheet) return null

      this._saveToHistory(worksheetName)

      const factory = defaultFactoryMap[worksheetName]
      const newRow = factory ? factory() : {}

      newRow._id = Date.now()
      newRow._isNew = true
      worksheet.data.push(newRow)
      worksheet.dirty = true

      return newRow
    },

    insertRow(worksheetName, index, row = null) {
      const worksheet = this.worksheets[worksheetName]
      if (!worksheet) return null

      this._saveToHistory(worksheetName)

      const newRow = row || this.addRow(worksheetName)
      if (newRow && index >= 0 && index < worksheet.data.length) {
        // Remove from end (where addRow placed it)
        worksheet.data.pop()
        // Insert at desired position
        worksheet.data.splice(index, 0, newRow)
      }

      return newRow
    },

    removeRow(worksheetName, rowIndex) {
      const worksheet = this.worksheets[worksheetName]
      if (!worksheet || rowIndex < 0 || rowIndex >= worksheet.data.length) return false

      this._saveToHistory(worksheetName)
      worksheet.data.splice(rowIndex, 1)
      worksheet.dirty = true

      return true
    },

    removeRows(worksheetName, indices) {
      const worksheet = this.worksheets[worksheetName]
      if (!worksheet) return false

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

    duplicateRow(worksheetName, rowIndex) {
      const worksheet = this.worksheets[worksheetName]
      if (!worksheet || rowIndex < 0 || rowIndex >= worksheet.data.length) return null

      this._saveToHistory(worksheetName)

      const original = worksheet.data[rowIndex]
      const duplicate = {
        ...JSON.parse(JSON.stringify(original)),
        _id: Date.now(),
        _isNew: true
      }

      // Clear identifiers that should be unique
      delete duplicate.id
      if (duplicate.order_number) {
        duplicate.order_number = `${duplicate.order_number}-COPY`
      }
      if (duplicate.line_code) {
        duplicate.line_code = `${duplicate.line_code}-COPY`
      }

      worksheet.data.splice(rowIndex + 1, 0, duplicate)
      worksheet.dirty = true

      return duplicate
    },

    importData(worksheetName, data) {
      const worksheet = this.worksheets[worksheetName]
      if (!worksheet) return false

      this._saveToHistory(worksheetName)

      worksheet.data = data.map((row, idx) => ({
        ...row,
        _id: row.id || (Date.now() + idx),
        _imported: true
      }))
      worksheet.dirty = true

      return true
    },

    appendData(worksheetName, data) {
      const worksheet = this.worksheets[worksheetName]
      if (!worksheet) return false

      this._saveToHistory(worksheetName)

      const newRows = data.map((row, idx) => ({
        ...row,
        _id: row.id || (Date.now() + idx),
        _imported: true
      }))

      worksheet.data = [...worksheet.data, ...newRows]
      worksheet.dirty = true

      return true
    },

    // ---- Dashboard Inputs ----

    updateDashboardInput(key, value) {
      this._saveToHistory('dashboardInputs')
      this.worksheets.dashboardInputs.data[key] = value
      this.worksheets.dashboardInputs.dirty = true
    },

    // ---- Export Helpers ----

    exportWorksheetJSON(worksheetName) {
      const worksheet = this.worksheets[worksheetName]
      if (!worksheet) return null

      const data = worksheetName === 'instructions' ? worksheet.content : worksheet.data

      const cleanData = Array.isArray(data)
        ? data.map(row => {
            const { _id, _isNew, _imported, ...clean } = row
            return clean
          })
        : data

      return JSON.stringify(cleanData, null, 2)
    },

    exportWorkbookJSON() {
      const workbook = {}

      for (const [key, worksheet] of Object.entries(this.worksheets)) {
        if (key === 'instructions') {
          workbook[key] = worksheet.content
        } else {
          workbook[key] = Array.isArray(worksheet.data)
            ? worksheet.data.map(row => {
                const { _id, _isNew, _imported, ...clean } = row
                return clean
              })
            : worksheet.data
        }
      }

      return JSON.stringify(workbook, null, 2)
    },

    // ---- BOM Operations ----

    addBOMComponent(bomIndex) {
      const bom = this.worksheets.bom.data[bomIndex]
      if (!bom) return null

      this._saveToHistory('bom')

      if (!bom.components) {
        bom.components = []
      }

      const newComponent = {
        ...getDefaultBOMDetail(),
        _id: Date.now()
      }

      bom.components.push(newComponent)
      this.worksheets.bom.dirty = true

      return newComponent
    },

    removeBOMComponent(bomIndex, componentIndex) {
      const bom = this.worksheets.bom.data[bomIndex]
      if (!bom || !bom.components || componentIndex < 0) return false

      this._saveToHistory('bom')
      bom.components.splice(componentIndex, 1)
      this.worksheets.bom.dirty = true

      return true
    },

    // ---- Reset Worksheets ----

    resetWorksheets() {
      Object.keys(this.worksheets).forEach(key => {
        if (key === 'instructions') {
          this.worksheets[key] = { content: '', dirty: false, loading: false, error: null }
        } else if (key === 'dashboardInputs') {
          this.worksheets[key] = {
            data: getDefaultDashboardInputs(),
            dirty: false,
            loading: false,
            error: null
          }
        } else {
          this.worksheets[key] = { data: [], dirty: false, loading: false, error: null }
        }
      })

      if (this._historyManager) {
        this._historyManager.clear()
      }
    },

    clearAllErrors() {
      Object.values(this.worksheets).forEach(ws => {
        ws.error = null
      })
    }
  }
})
