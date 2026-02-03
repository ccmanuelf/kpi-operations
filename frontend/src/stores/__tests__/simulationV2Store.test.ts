/**
 * Unit tests for simulationV2Store
 *
 * Tests the Pinia store for the Production Line Simulation v2.0 feature.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useSimulationV2Store } from '../simulationV2Store'

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {}
  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key]
    }),
    clear: vi.fn(() => {
      store = {}
    })
  }
})()
Object.defineProperty(window, 'localStorage', { value: localStorageMock })

// Mock the API module
vi.mock('@/services/api/simulationV2', () => ({
  getSimulationInfo: vi.fn(() => Promise.resolve({ version: '2.0.0' })),
  validateSimulationConfig: vi.fn(() =>
    Promise.resolve({
      is_valid: true,
      errors: [],
      warnings: [],
      info: [],
      products_count: 1,
      operations_count: 3,
      machine_tools_count: 3
    })
  ),
  runSimulation: vi.fn(() =>
    Promise.resolve({
      success: true,
      message: 'Simulation completed',
      results: {
        block1_weekly_demand_capacity: [],
        block2_daily_summary: {},
        block3_station_performance: [],
        block4_free_capacity: [],
        block5_bundle_metrics: {},
        block6_per_product: [],
        block7_rebalancing: [],
        block8_assumptions: []
      },
      validation_report: { is_valid: true, errors: [], warnings: [], info: [] }
    })
  ),
  buildSimulationConfig: vi.fn((config) => config),
  getDefaultOperation: vi.fn((product = '') => ({
    product,
    step: 1,
    operation: '',
    machine_tool: '',
    sam_min: 1.0,
    operators: 1,
    grade_pct: 85,
    fpd_pct: 2,
    variability_pct: 10
  })),
  getDefaultSchedule: vi.fn(() => ({
    shifts_enabled: 1,
    shift1_hours: 8,
    shift2_hours: 0,
    shift3_hours: 0,
    work_days: 5,
    ot_enabled: false,
    weekday_ot_hours: 0,
    weekend_ot_days: 0,
    weekend_ot_hours: 0
  })),
  getDefaultDemand: vi.fn((product = '') => ({
    product,
    daily_demand: null,
    weekly_demand: null,
    bundle_size: 10,
    mix_share_pct: null
  })),
  getDefaultBreakdown: vi.fn((machineTool = '') => ({
    machine_tool: machineTool,
    breakdown_pct: 2.0
  })),
  getSampleTShirtData: vi.fn(() => ({
    operations: [
      { product: 'Basic T-Shirt', step: 1, operation: 'Cut Fabric Panels', machine_tool: 'Cutting Table', sam_min: 0.8, operators: 2, grade_pct: 90, fpd_pct: 5 },
      { product: 'Basic T-Shirt', step: 2, operation: 'Attach Collar', machine_tool: 'Serger Machine', sam_min: 1.2, operators: 1, grade_pct: 85, fpd_pct: 12 }
    ],
    schedule: { shifts_enabled: 1, shift1_hours: 8, shift2_hours: 0, shift3_hours: 0, work_days: 5, ot_enabled: false },
    demands: [{ product: 'Basic T-Shirt', bundle_size: 12, daily_demand: 500 }],
    breakdowns: [{ machine_tool: 'Serger Machine', breakdown_pct: 3 }],
    mode: 'demand-driven',
    horizon_days: 5
  })),
  isFirstVisit: vi.fn(() => true),
  markAsVisited: vi.fn(),
  clearVisitedFlag: vi.fn()
}))

describe('simulationV2Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  describe('Initial State', () => {
    it('should have correct initial state', () => {
      const store = useSimulationV2Store()

      expect(store.operations).toEqual([])
      expect(store.demands).toEqual([])
      expect(store.breakdowns).toEqual([])
      expect(store.mode).toBe('demand-driven')
      expect(store.totalDemand).toBeNull()
      expect(store.horizonDays).toBe(1)
      expect(store.validationReport).toBeNull()
      expect(store.results).toBeNull()
      expect(store.isValidating).toBe(false)
      expect(store.isRunning).toBe(false)
      expect(store.error).toBeNull()
    })

    it('should have default schedule configuration', () => {
      const store = useSimulationV2Store()

      expect(store.schedule.shifts_enabled).toBe(1)
      expect(store.schedule.shift1_hours).toBe(8)
      expect(store.schedule.work_days).toBe(5)
      expect(store.schedule.ot_enabled).toBe(false)
    })
  })

  describe('Getters', () => {
    it('should return false for canRun when no operations', () => {
      const store = useSimulationV2Store()
      expect(store.canRun).toBe(false)
    })

    it('should return false for canRun when no demands', () => {
      const store = useSimulationV2Store()
      store.addOperation({ product: 'Test', step: 1, operation: 'Op1', machine_tool: 'M1', sam_min: 2, operators: 1, grade_pct: 85, fpd_pct: 2 })
      expect(store.canRun).toBe(false)
    })

    it('should return true for canRun when operations and demands exist', () => {
      const store = useSimulationV2Store()
      store.addOperation({ product: 'Test', step: 1, operation: 'Op1', machine_tool: 'M1', sam_min: 2, operators: 1, grade_pct: 85, fpd_pct: 2 })
      store.addDemand({ product: 'Test', daily_demand: 100, bundle_size: 10 })
      expect(store.canRun).toBe(true)
    })

    it('should extract unique products from operations', () => {
      const store = useSimulationV2Store()
      store.addOperation({ product: 'A', step: 1, operation: 'Op1', machine_tool: 'M1', sam_min: 2, operators: 1, grade_pct: 85, fpd_pct: 2 })
      store.addOperation({ product: 'A', step: 2, operation: 'Op2', machine_tool: 'M2', sam_min: 3, operators: 1, grade_pct: 85, fpd_pct: 2 })
      store.addOperation({ product: 'B', step: 1, operation: 'Op1', machine_tool: 'M1', sam_min: 2, operators: 1, grade_pct: 85, fpd_pct: 2 })

      expect(store.products).toHaveLength(2)
      expect(store.products).toContain('A')
      expect(store.products).toContain('B')
    })

    it('should extract unique machine tools from operations', () => {
      const store = useSimulationV2Store()
      store.addOperation({ product: 'A', step: 1, operation: 'Op1', machine_tool: 'Cutter', sam_min: 2, operators: 1, grade_pct: 85, fpd_pct: 2 })
      store.addOperation({ product: 'A', step: 2, operation: 'Op2', machine_tool: 'Assembly', sam_min: 3, operators: 1, grade_pct: 85, fpd_pct: 2 })
      store.addOperation({ product: 'B', step: 1, operation: 'Op1', machine_tool: 'Cutter', sam_min: 2, operators: 1, grade_pct: 85, fpd_pct: 2 })

      expect(store.machineTools).toHaveLength(2)
      expect(store.machineTools).toContain('Cutter')
      expect(store.machineTools).toContain('Assembly')
    })

    it('should group operations by product', () => {
      const store = useSimulationV2Store()
      store.addOperation({ product: 'A', step: 1, operation: 'Op1', machine_tool: 'M1', sam_min: 2, operators: 1, grade_pct: 85, fpd_pct: 2 })
      store.addOperation({ product: 'A', step: 2, operation: 'Op2', machine_tool: 'M2', sam_min: 3, operators: 1, grade_pct: 85, fpd_pct: 2 })
      store.addOperation({ product: 'B', step: 1, operation: 'Op1', machine_tool: 'M1', sam_min: 2, operators: 1, grade_pct: 85, fpd_pct: 2 })

      const grouped = store.operationsByProduct
      expect(Object.keys(grouped)).toHaveLength(2)
      expect(grouped['A']).toHaveLength(2)
      expect(grouped['B']).toHaveLength(1)
    })

    it('should calculate daily planned hours from schedule', () => {
      const store = useSimulationV2Store()

      // Default: 1 shift of 8 hours
      expect(store.dailyPlannedHours).toBe(8)

      // Enable 2 shifts
      store.schedule.shifts_enabled = 2
      store.schedule.shift2_hours = 8
      expect(store.dailyPlannedHours).toBe(16)

      // Enable 3 shifts
      store.schedule.shifts_enabled = 3
      store.schedule.shift3_hours = 8
      expect(store.dailyPlannedHours).toBe(24)
    })

    it('should calculate total mix percent', () => {
      const store = useSimulationV2Store()
      store.addDemand({ product: 'A', mix_share_pct: 60 })
      store.addDemand({ product: 'B', mix_share_pct: 40 })

      expect(store.totalMixPercent).toBe(100)
    })

    it('should count operations correctly', () => {
      const store = useSimulationV2Store()
      store.addOperation({ product: 'A', step: 1, operation: 'Op1', machine_tool: 'M1', sam_min: 2, operators: 1, grade_pct: 85, fpd_pct: 2 })
      store.addOperation({ product: 'A', step: 2, operation: 'Op2', machine_tool: 'M2', sam_min: 3, operators: 1, grade_pct: 85, fpd_pct: 2 })

      expect(store.operationsCount).toBe(2)
    })

    it('should count products correctly', () => {
      const store = useSimulationV2Store()
      store.addOperation({ product: 'A', step: 1, operation: 'Op1', machine_tool: 'M1', sam_min: 2, operators: 1, grade_pct: 85, fpd_pct: 2 })
      store.addOperation({ product: 'B', step: 1, operation: 'Op1', machine_tool: 'M1', sam_min: 2, operators: 1, grade_pct: 85, fpd_pct: 2 })

      expect(store.productsCount).toBe(2)
    })
  })

  describe('Operations Actions', () => {
    it('should add operation', () => {
      const store = useSimulationV2Store()
      store.addOperation({ product: 'Test', step: 1, operation: 'Cut', machine_tool: 'Cutter', sam_min: 2.5, operators: 2, grade_pct: 85, fpd_pct: 3 })

      expect(store.operations).toHaveLength(1)
      expect(store.operations[0].product).toBe('Test')
      expect(store.operations[0].operation).toBe('Cut')
      expect(store.operations[0]._id).toBeDefined()
    })

    it('should auto-increment step for same product', () => {
      const store = useSimulationV2Store()
      store.addOperation({ product: 'Test', step: 1, operation: 'Cut', machine_tool: 'Cutter', sam_min: 2.5, operators: 2, grade_pct: 85, fpd_pct: 3 })
      store.addOperation() // Add with defaults

      expect(store.operations).toHaveLength(2)
    })

    it('should update operation', () => {
      const store = useSimulationV2Store()
      store.addOperation({ product: 'Test', step: 1, operation: 'Cut', machine_tool: 'Cutter', sam_min: 2.5, operators: 2, grade_pct: 85, fpd_pct: 3 })
      store.updateOperation(0, { sam_min: 5.0 })

      expect(store.operations[0].sam_min).toBe(5.0)
    })

    it('should remove operation', () => {
      const store = useSimulationV2Store()
      store.addOperation({ product: 'Test', step: 1, operation: 'Cut', machine_tool: 'Cutter', sam_min: 2.5, operators: 2, grade_pct: 85, fpd_pct: 3 })
      store.addOperation({ product: 'Test', step: 2, operation: 'Pack', machine_tool: 'Packer', sam_min: 1.5, operators: 1, grade_pct: 90, fpd_pct: 1 })

      store.removeOperation(0)

      expect(store.operations).toHaveLength(1)
      expect(store.operations[0].operation).toBe('Pack')
    })

    it('should import operations', () => {
      const store = useSimulationV2Store()
      const operations = [
        { product: 'A', step: 1, operation: 'Op1', machine_tool: 'M1', sam_min: 2, operators: 1, grade_pct: 85, fpd_pct: 2 },
        { product: 'A', step: 2, operation: 'Op2', machine_tool: 'M2', sam_min: 3, operators: 2, grade_pct: 80, fpd_pct: 5 }
      ]

      store.importOperations(operations)

      expect(store.operations).toHaveLength(2)
      expect(store.operations[0]._id).toBeDefined()
      expect(store.operations[1]._id).toBeDefined()
    })
  })

  describe('Demand Actions', () => {
    it('should add demand', () => {
      const store = useSimulationV2Store()
      store.addDemand({ product: 'Test', daily_demand: 100, bundle_size: 10 })

      expect(store.demands).toHaveLength(1)
      expect(store.demands[0].product).toBe('Test')
      expect(store.demands[0].daily_demand).toBe(100)
    })

    it('should update demand', () => {
      const store = useSimulationV2Store()
      store.addDemand({ product: 'Test', daily_demand: 100, bundle_size: 10 })
      store.updateDemand(0, { daily_demand: 200 })

      expect(store.demands[0].daily_demand).toBe(200)
    })

    it('should remove demand', () => {
      const store = useSimulationV2Store()
      store.addDemand({ product: 'A', daily_demand: 100 })
      store.addDemand({ product: 'B', daily_demand: 200 })

      store.removeDemand(0)

      expect(store.demands).toHaveLength(1)
      expect(store.demands[0].product).toBe('B')
    })

    it('should import demands', () => {
      const store = useSimulationV2Store()
      const demands = [
        { product: 'A', daily_demand: 100, bundle_size: 10 },
        { product: 'B', daily_demand: 200, bundle_size: 20 }
      ]

      store.importDemands(demands)

      expect(store.demands).toHaveLength(2)
    })
  })

  describe('Breakdown Actions', () => {
    it('should add breakdown', () => {
      const store = useSimulationV2Store()
      store.addBreakdown({ machine_tool: 'Cutter', breakdown_pct: 2.5 })

      expect(store.breakdowns).toHaveLength(1)
      expect(store.breakdowns[0].machine_tool).toBe('Cutter')
    })

    it('should update breakdown', () => {
      const store = useSimulationV2Store()
      store.addBreakdown({ machine_tool: 'Cutter', breakdown_pct: 2.5 })
      store.updateBreakdown(0, { breakdown_pct: 5.0 })

      expect(store.breakdowns[0].breakdown_pct).toBe(5.0)
    })

    it('should remove breakdown', () => {
      const store = useSimulationV2Store()
      store.addBreakdown({ machine_tool: 'Cutter', breakdown_pct: 2.5 })
      store.addBreakdown({ machine_tool: 'Assembly', breakdown_pct: 1.0 })

      store.removeBreakdown(0)

      expect(store.breakdowns).toHaveLength(1)
      expect(store.breakdowns[0].machine_tool).toBe('Assembly')
    })
  })

  describe('Schedule Actions', () => {
    it('should update schedule', () => {
      const store = useSimulationV2Store()
      store.updateSchedule({ shift1_hours: 10, work_days: 6 })

      expect(store.schedule.shift1_hours).toBe(10)
      expect(store.schedule.work_days).toBe(6)
    })
  })

  describe('Mode Actions', () => {
    it('should set mode', () => {
      const store = useSimulationV2Store()
      store.setMode('mix-driven')

      expect(store.mode).toBe('mix-driven')
    })

    it('should clear totalDemand when switching to demand-driven', () => {
      const store = useSimulationV2Store()
      store.totalDemand = 1000
      store.setMode('demand-driven')

      expect(store.totalDemand).toBeNull()
    })
  })

  describe('Reset Action', () => {
    it('should reset all state', () => {
      const store = useSimulationV2Store()

      // Add some data
      store.addOperation({ product: 'Test', step: 1, operation: 'Op1', machine_tool: 'M1', sam_min: 2, operators: 1, grade_pct: 85, fpd_pct: 2 })
      store.addDemand({ product: 'Test', daily_demand: 100 })
      store.addBreakdown({ machine_tool: 'M1', breakdown_pct: 2.0 })
      store.mode = 'mix-driven'
      store.horizonDays = 7

      // Reset
      store.reset()

      // Verify reset
      expect(store.operations).toEqual([])
      expect(store.demands).toEqual([])
      expect(store.breakdowns).toEqual([])
      expect(store.mode).toBe('demand-driven')
      expect(store.horizonDays).toBe(1)
      expect(store.validationReport).toBeNull()
      expect(store.results).toBeNull()
      expect(store.error).toBeNull()
    })
  })

  describe('Load Configuration', () => {
    it('should load full configuration', () => {
      const store = useSimulationV2Store()

      const config = {
        operations: [
          { product: 'A', step: 1, operation: 'Op1', machine_tool: 'M1', sam_min: 2, operators: 1, grade_pct: 85, fpd_pct: 2 }
        ],
        schedule: {
          shifts_enabled: 2,
          shift1_hours: 8,
          shift2_hours: 8,
          work_days: 6
        },
        demands: [
          { product: 'A', daily_demand: 100, bundle_size: 10 }
        ],
        breakdowns: [
          { machine_tool: 'M1', breakdown_pct: 2.0 }
        ],
        mode: 'mix-driven',
        total_demand: 500,
        horizon_days: 5
      }

      store.loadConfiguration(config)

      expect(store.operations).toHaveLength(1)
      expect(store.demands).toHaveLength(1)
      expect(store.breakdowns).toHaveLength(1)
      expect(store.schedule.shifts_enabled).toBe(2)
      expect(store.mode).toBe('mix-driven')
      expect(store.totalDemand).toBe(500)
      expect(store.horizonDays).toBe(5)
    })

    it('should load partial configuration', () => {
      const store = useSimulationV2Store()

      const config = {
        operations: [
          { product: 'A', step: 1, operation: 'Op1', machine_tool: 'M1', sam_min: 2, operators: 1, grade_pct: 85, fpd_pct: 2 }
        ]
      }

      store.loadConfiguration(config)

      expect(store.operations).toHaveLength(1)
      expect(store.demands).toHaveLength(0) // Not provided, should be empty
    })
  })

  describe('Export Configuration', () => {
    it('should export configuration', () => {
      const store = useSimulationV2Store()

      store.addOperation({ product: 'A', step: 1, operation: 'Op1', machine_tool: 'M1', sam_min: 2, operators: 1, grade_pct: 85, fpd_pct: 2 })
      store.addDemand({ product: 'A', daily_demand: 100 })

      const exported = store.exportConfiguration()

      expect(exported).toBeDefined()
      expect(exported.operations).toBeDefined()
    })
  })

  describe('Validation', () => {
    it('should validate configuration', async () => {
      const store = useSimulationV2Store()

      store.addOperation({ product: 'A', step: 1, operation: 'Op1', machine_tool: 'M1', sam_min: 2, operators: 1, grade_pct: 85, fpd_pct: 2 })
      store.addDemand({ product: 'A', daily_demand: 100 })

      const result = await store.validate()

      expect(result.is_valid).toBe(true)
      expect(store.validationReport).toBeDefined()
      expect(store.showValidationPanel).toBe(true)
    })

    it('should set isValidating flag during validation', async () => {
      const store = useSimulationV2Store()

      store.addOperation({ product: 'A', step: 1, operation: 'Op1', machine_tool: 'M1', sam_min: 2, operators: 1, grade_pct: 85, fpd_pct: 2 })

      const validatePromise = store.validate()

      // Should be validating
      expect(store.isValidating).toBe(true)

      await validatePromise

      // Should be done
      expect(store.isValidating).toBe(false)
    })
  })

  describe('Run Simulation', () => {
    it('should run simulation', async () => {
      const store = useSimulationV2Store()

      store.addOperation({ product: 'A', step: 1, operation: 'Op1', machine_tool: 'M1', sam_min: 2, operators: 1, grade_pct: 85, fpd_pct: 2 })
      store.addDemand({ product: 'A', daily_demand: 100 })

      const result = await store.run()

      expect(result.success).toBe(true)
      expect(store.results).toBeDefined()
      expect(store.showResultsDialog).toBe(true)
    })

    it('should set isRunning flag during simulation', async () => {
      const store = useSimulationV2Store()

      store.addOperation({ product: 'A', step: 1, operation: 'Op1', machine_tool: 'M1', sam_min: 2, operators: 1, grade_pct: 85, fpd_pct: 2 })
      store.addDemand({ product: 'A', daily_demand: 100 })

      const runPromise = store.run()

      // Should be running
      expect(store.isRunning).toBe(true)

      await runPromise

      // Should be done
      expect(store.isRunning).toBe(false)
    })
  })

  describe('Error Handling', () => {
    it('should handle validation errors', async () => {
      const { validateSimulationConfig } = await import('@/services/api/simulationV2')
      vi.mocked(validateSimulationConfig).mockRejectedValueOnce(new Error('Validation failed'))

      const store = useSimulationV2Store()
      store.addOperation({ product: 'A', step: 1, operation: 'Op1', machine_tool: 'M1', sam_min: 2, operators: 1, grade_pct: 85, fpd_pct: 2 })

      await expect(store.validate()).rejects.toThrow()
      expect(store.error).toBeDefined()
    })

    it('should handle simulation errors', async () => {
      const { runSimulation } = await import('@/services/api/simulationV2')
      vi.mocked(runSimulation).mockRejectedValueOnce(new Error('Simulation failed'))

      const store = useSimulationV2Store()
      store.addOperation({ product: 'A', step: 1, operation: 'Op1', machine_tool: 'M1', sam_min: 2, operators: 1, grade_pct: 85, fpd_pct: 2 })
      store.addDemand({ product: 'A', daily_demand: 100 })

      await expect(store.run()).rejects.toThrow()
      expect(store.error).toBeDefined()
    })
  })

  describe('Sample Data Actions', () => {
    beforeEach(() => {
      localStorageMock.clear()
    })

    it('should load sample T-Shirt data', () => {
      const store = useSimulationV2Store()
      store.loadSampleData()

      expect(store.operations.length).toBeGreaterThan(0)
      expect(store.operations[0].product).toBe('Basic T-Shirt')
      expect(store.demands.length).toBeGreaterThan(0)
      expect(store.breakdowns.length).toBeGreaterThan(0)
    })

    it('should check first visit status', () => {
      const store = useSimulationV2Store()
      const result = store.isFirstVisit()

      expect(result).toBe(true)
    })

    it('should reset to sample data', () => {
      const store = useSimulationV2Store()

      // Add some custom data
      store.addOperation({ product: 'Custom', step: 1, operation: 'Op1', machine_tool: 'M1', sam_min: 2, operators: 1, grade_pct: 85, fpd_pct: 2 })

      // Reset to sample
      store.resetToSample()

      // Should have sample data, not custom data
      expect(store.operations[0].product).toBe('Basic T-Shirt')
    })

    it('should mark as visited after loading sample data', async () => {
      const { markAsVisited } = await import('@/services/api/simulationV2')
      const store = useSimulationV2Store()

      store.loadSampleData()

      expect(markAsVisited).toHaveBeenCalled()
    })
  })
})
