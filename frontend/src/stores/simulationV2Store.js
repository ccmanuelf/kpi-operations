/**
 * Production Line Simulation v2.0 - Pinia Store
 *
 * State management for the ephemeral simulation tool.
 * Manages configuration input, validation, and results.
 */

import { defineStore } from 'pinia'
import {
  getSimulationInfo,
  validateSimulationConfig,
  runSimulation,
  buildSimulationConfig,
  getDefaultOperation,
  getDefaultSchedule,
  getDefaultDemand,
  getDefaultBreakdown,
  getSampleTShirtData,
  isFirstVisit,
  markAsVisited,
  clearVisitedFlag
} from '@/services/api/simulationV2'

export const useSimulationV2Store = defineStore('simulationV2', {
  state: () => ({
    // Tool metadata
    toolInfo: null,

    // Configuration input
    operations: [],
    schedule: getDefaultSchedule(),
    demands: [],
    breakdowns: [],
    mode: 'demand-driven', // 'demand-driven' or 'mix-driven'
    totalDemand: null,
    horizonDays: 1,

    // Validation state
    validationReport: null,
    isValidating: false,

    // Simulation state
    isRunning: false,
    results: null,
    simulationMessage: '',

    // UI state
    activeTab: 'operations',
    showValidationPanel: false,
    showResultsDialog: false,

    // Error handling
    error: null
  }),

  getters: {
    /**
     * Check if configuration is valid for running
     */
    canRun: (state) => {
      return state.operations.length > 0 &&
             state.demands.length > 0 &&
             !state.isRunning &&
             (!state.validationReport || state.validationReport.is_valid)
    },

    /**
     * Get unique products from operations
     */
    products: (state) => {
      return [...new Set(state.operations.map(op => op.product))].filter(Boolean)
    },

    /**
     * Get unique machine tools from operations
     */
    machineTools: (state) => {
      return [...new Set(state.operations.map(op => op.machine_tool))].filter(Boolean)
    },

    /**
     * Get operations grouped by product
     */
    operationsByProduct: (state) => {
      const grouped = {}
      for (const op of state.operations) {
        if (!grouped[op.product]) {
          grouped[op.product] = []
        }
        grouped[op.product].push(op)
      }
      // Sort each product's operations by step
      for (const product in grouped) {
        grouped[product].sort((a, b) => a.step - b.step)
      }
      return grouped
    },

    /**
     * Get total operation count
     */
    operationsCount: (state) => state.operations.length,

    /**
     * Get products count
     */
    productsCount: (state) => {
      return new Set(state.operations.map(op => op.product).filter(Boolean)).size
    },

    /**
     * Check if there are validation errors
     */
    hasValidationErrors: (state) => {
      return state.validationReport?.errors?.length > 0
    },

    /**
     * Check if there are validation warnings
     */
    hasValidationWarnings: (state) => {
      return state.validationReport?.warnings?.length > 0
    },

    /**
     * Calculate total daily hours from schedule
     */
    dailyPlannedHours: (state) => {
      let hours = Number(state.schedule.shift1_hours) || 0
      if (state.schedule.shifts_enabled >= 2) {
        hours += Number(state.schedule.shift2_hours) || 0
      }
      if (state.schedule.shifts_enabled >= 3) {
        hours += Number(state.schedule.shift3_hours) || 0
      }
      return hours
    },

    /**
     * Get mix percentage total
     */
    totalMixPercent: (state) => {
      return state.demands.reduce((sum, d) => sum + (parseFloat(d.mix_share_pct) || 0), 0)
    }
  },

  actions: {
    /**
     * Fetch tool info from API
     */
    async fetchToolInfo() {
      try {
        this.toolInfo = await getSimulationInfo()
      } catch (error) {
        console.error('Failed to fetch simulation info:', error)
        this.error = error.message
      }
    },

    /**
     * Add a new operation row
     */
    addOperation(operation = null) {
      const newOp = operation || getDefaultOperation(this.products[0] || '')
      // Auto-increment step for same product
      const sameProductOps = this.operations.filter(op => op.product === newOp.product)
      if (sameProductOps.length > 0 && !operation) {
        newOp.step = Math.max(...sameProductOps.map(op => op.step)) + 1
      }
      this.operations.push({ ...newOp, _id: Date.now() })
    },

    /**
     * Update an operation
     */
    updateOperation(index, updates) {
      if (this.operations[index]) {
        Object.assign(this.operations[index], updates)
      }
    },

    /**
     * Remove an operation
     */
    removeOperation(index) {
      this.operations.splice(index, 1)
    },

    /**
     * Import operations from array (e.g., CSV paste)
     */
    importOperations(operations) {
      this.operations = operations.map((op, idx) => ({
        ...getDefaultOperation(),
        ...op,
        _id: Date.now() + idx
      }))
    },

    /**
     * Update schedule configuration
     */
    updateSchedule(updates) {
      Object.assign(this.schedule, updates)
    },

    /**
     * Add a new demand row
     */
    addDemand(demand = null) {
      const newDemand = demand || getDefaultDemand('')
      this.demands.push({ ...newDemand, _id: Date.now() })
    },

    /**
     * Update a demand
     */
    updateDemand(index, updates) {
      if (this.demands[index]) {
        Object.assign(this.demands[index], updates)
      }
    },

    /**
     * Remove a demand
     */
    removeDemand(index) {
      this.demands.splice(index, 1)
    },

    /**
     * Import demands from array
     */
    importDemands(demands) {
      this.demands = demands.map((d, idx) => ({
        ...getDefaultDemand(),
        ...d,
        _id: Date.now() + idx
      }))
    },

    /**
     * Add a breakdown configuration
     */
    addBreakdown(breakdown = null) {
      const newBreakdown = breakdown || getDefaultBreakdown('')
      this.breakdowns.push({ ...newBreakdown, _id: Date.now() })
    },

    /**
     * Update a breakdown
     */
    updateBreakdown(index, updates) {
      if (this.breakdowns[index]) {
        Object.assign(this.breakdowns[index], updates)
      }
    },

    /**
     * Remove a breakdown
     */
    removeBreakdown(index) {
      this.breakdowns.splice(index, 1)
    },

    /**
     * Set demand mode
     */
    setMode(mode) {
      this.mode = mode
      // Clear mix percentages when switching to demand-driven
      if (mode === 'demand-driven') {
        this.totalDemand = null
      }
    },

    /**
     * Build configuration object for API
     */
    buildConfig() {
      return buildSimulationConfig({
        operations: this.operations,
        schedule: this.schedule,
        demands: this.demands,
        breakdowns: this.breakdowns,
        mode: this.mode,
        totalDemand: this.totalDemand,
        horizonDays: this.horizonDays
      })
    },

    /**
     * Validate configuration
     */
    async validate() {
      this.isValidating = true
      this.error = null
      this.validationReport = null

      try {
        const config = this.buildConfig()
        this.validationReport = await validateSimulationConfig(config)
        this.showValidationPanel = true
        return this.validationReport
      } catch (error) {
        console.error('Validation failed:', error)
        this.error = error.response?.data?.detail || error.message
        throw error
      } finally {
        this.isValidating = false
      }
    },

    /**
     * Run simulation
     */
    async run() {
      this.isRunning = true
      this.error = null
      this.results = null
      this.simulationMessage = ''

      try {
        const config = this.buildConfig()
        const response = await runSimulation(config)

        if (response.success) {
          this.results = response.results
          this.simulationMessage = response.message
          this.validationReport = response.validation_report
          this.showResultsDialog = true
        } else {
          this.validationReport = response.validation_report
          this.simulationMessage = response.message
          this.showValidationPanel = true
        }

        return response
      } catch (error) {
        console.error('Simulation failed:', error)
        this.error = error.response?.data?.detail || error.message
        throw error
      } finally {
        this.isRunning = false
      }
    },

    /**
     * Reset all configuration
     */
    reset() {
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
    },

    /**
     * Load configuration from JSON
     */
    loadConfiguration(config) {
      if (config.operations) {
        this.operations = config.operations.map((op, idx) => ({
          ...getDefaultOperation(),
          ...op,
          _id: Date.now() + idx
        }))
      }
      if (config.schedule) {
        this.schedule = { ...getDefaultSchedule(), ...config.schedule }
      }
      if (config.demands) {
        this.demands = config.demands.map((d, idx) => ({
          ...getDefaultDemand(),
          ...d,
          _id: Date.now() + idx
        }))
      }
      if (config.breakdowns) {
        this.breakdowns = config.breakdowns.map((b, idx) => ({
          ...getDefaultBreakdown(),
          ...b,
          _id: Date.now() + idx
        }))
      }
      if (config.mode) {
        this.mode = config.mode
      }
      if (config.total_demand) {
        this.totalDemand = config.total_demand
      }
      if (config.horizon_days) {
        this.horizonDays = config.horizon_days
      }
    },

    /**
     * Export current configuration as JSON
     */
    exportConfiguration() {
      return this.buildConfig()
    },

    /**
     * Load sample T-Shirt manufacturing data for onboarding
     * Provides realistic data to help users understand the tool
     */
    loadSampleData() {
      const sampleData = getSampleTShirtData()
      this.loadConfiguration(sampleData)
      // Mark as visited so sample data doesn't auto-load again
      markAsVisited()
    },

    /**
     * Check if this is user's first visit to the simulation tool
     */
    isFirstVisit() {
      return isFirstVisit()
    },

    /**
     * Reset to sample data (for "Load Sample" button)
     */
    resetToSample() {
      this.reset()
      this.loadSampleData()
    },

    /**
     * Clear first-visit flag (for testing purposes)
     */
    clearFirstVisitFlag() {
      clearVisitedFlag()
    }
  }
})
