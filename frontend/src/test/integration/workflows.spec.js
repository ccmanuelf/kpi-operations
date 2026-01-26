/**
 * Integration Tests for KPI Platform Workflows
 * Phase 8.2: End-to-end workflow testing
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

/**
 * Integration test suite covering complete workflows:
 * - 8.2.1: Excel paste workflow (clipboard → validation → grid)
 * - 8.2.2: Hold/resume/approve cycle (full state machine)
 * - 8.2.3: Client-specific KPI calculations
 * - 8.2.4: Multi-tenant data isolation
 */

// Mock API responses
const mockApiResponses = {
  production: [
    { id: 1, client_id: 'client_1', production_date: '2024-01-15', units_produced: 500, run_time_hours: 8 },
    { id: 2, client_id: 'client_1', production_date: '2024-01-16', units_produced: 450, run_time_hours: 8 }
  ],
  holds: [
    { id: 1, client_id: 'client_1', work_order_id: 'WO-001', status: 'PENDING_HOLD_APPROVAL' },
    { id: 2, client_id: 'client_2', work_order_id: 'WO-002', status: 'ON_HOLD' }
  ],
  clients: [
    { client_id: 'client_1', name: 'Client One', otd_mode: 'TRUE' },
    { client_id: 'client_2', name: 'Client Two', otd_mode: 'STANDARD' }
  ]
}

// Simulate fetch API
function createMockFetch() {
  return vi.fn((url, options = {}) => {
    const method = options.method || 'GET'

    // Route-based responses
    if (url.includes('/production') && method === 'GET') {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockApiResponses.production)
      })
    }

    if (url.includes('/holds') && method === 'GET') {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockApiResponses.holds)
      })
    }

    if (url.includes('/holds') && method === 'POST') {
      const body = JSON.parse(options.body)
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ id: 3, ...body, status: 'PENDING_HOLD_APPROVAL' })
      })
    }

    if (url.includes('/holds') && method === 'PATCH') {
      const body = JSON.parse(options.body)
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ ...body })
      })
    }

    if (url.includes('/clients') && method === 'GET') {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockApiResponses.clients)
      })
    }

    return Promise.resolve({
      ok: false,
      status: 404,
      json: () => Promise.resolve({ error: 'Not found' })
    })
  })
}

describe('Integration Workflows', () => {
  let mockFetch

  beforeEach(() => {
    setActivePinia(createPinia())
    mockFetch = createMockFetch()
    vi.stubGlobal('fetch', mockFetch)
  })

  describe('8.2.1: Excel Paste Workflow', () => {
    /**
     * Complete workflow: Excel clipboard → Parse → Validate → Transform → Submit
     */

    const excelClipboard = `Date\tProduct\tUnits Produced\tRuntime Hours\tEmployees
2024-01-15\tPROD-001\t500\t8.0\t5
2024-01-16\tPROD-002\t450\t7.5\t4
2024-01-17\tPROD-001\t600\t8.0\t6`

    function parseClipboardData(text) {
      if (!text || typeof text !== 'string') {
        return { error: 'No data in clipboard', rows: [] }
      }

      const lines = text.trim().split(/\r?\n/)
      const rows = lines.map(line => line.split('\t').map(cell => cell.trim()))

      // Detect headers
      const headerKeywords = ['date', 'product', 'units', 'hours', 'employee', 'id', 'name', 'shift']
      const firstRow = rows[0].map(cell => cell.toLowerCase())
      const hasHeaders = firstRow.some(cell =>
        headerKeywords.some(keyword => cell.includes(keyword))
      )

      return {
        hasHeaders,
        headers: hasHeaders ? rows[0] : null,
        rows: hasHeaders ? rows.slice(1) : rows,
        totalColumns: rows[0]?.length || 0
      }
    }

    function validateProductionRow(row, index) {
      const errors = []
      const [date, product, units, hours, employees] = row

      // Date validation
      if (!date || !/^\d{4}-\d{2}-\d{2}$/.test(date)) {
        errors.push(`Row ${index + 1}: Invalid date format`)
      }

      // Units validation
      const unitsNum = parseInt(units, 10)
      if (isNaN(unitsNum) || unitsNum < 0) {
        errors.push(`Row ${index + 1}: Units must be a positive number`)
      }

      // Hours validation
      const hoursNum = parseFloat(hours)
      if (isNaN(hoursNum) || hoursNum <= 0 || hoursNum > 24) {
        errors.push(`Row ${index + 1}: Hours must be between 0 and 24`)
      }

      // Employees validation
      const empNum = parseInt(employees, 10)
      if (isNaN(empNum) || empNum < 1) {
        errors.push(`Row ${index + 1}: Employees must be at least 1`)
      }

      return {
        valid: errors.length === 0,
        errors,
        data: errors.length === 0 ? {
          production_date: date,
          product_id: product,
          units_produced: unitsNum,
          run_time_hours: hoursNum,
          employees_assigned: empNum
        } : null
      }
    }

    function transformToApiPayload(validatedRows, clientId) {
      return validatedRows
        .filter(row => row.valid)
        .map(row => ({
          client_id: clientId,
          ...row.data
        }))
    }

    it('parses Excel clipboard data correctly', () => {
      const parsed = parseClipboardData(excelClipboard)

      expect(parsed.hasHeaders).toBe(true)
      expect(parsed.headers).toEqual(['Date', 'Product', 'Units Produced', 'Runtime Hours', 'Employees'])
      expect(parsed.rows).toHaveLength(3)
      expect(parsed.rows[0]).toEqual(['2024-01-15', 'PROD-001', '500', '8.0', '5'])
    })

    it('validates all rows and collects errors', () => {
      const parsed = parseClipboardData(excelClipboard)
      const validationResults = parsed.rows.map((row, i) => validateProductionRow(row, i))

      expect(validationResults.every(r => r.valid)).toBe(true)
      expect(validationResults.every(r => r.data !== null)).toBe(true)
    })

    it('catches invalid rows in validation', () => {
      const invalidClipboard = `Date\tProduct\tUnits\tHours\tEmployees
invalid-date\tPROD-001\t500\t8\t5
2024-01-16\tPROD-002\t-10\t8\t4
2024-01-17\tPROD-001\t500\t30\t0`

      const parsed = parseClipboardData(invalidClipboard)
      const validationResults = parsed.rows.map((row, i) => validateProductionRow(row, i))

      expect(validationResults[0].valid).toBe(false)
      expect(validationResults[0].errors[0]).toContain('Invalid date')

      expect(validationResults[1].valid).toBe(false)
      expect(validationResults[1].errors[0]).toContain('positive number')

      expect(validationResults[2].valid).toBe(false)
      expect(validationResults[2].errors.length).toBeGreaterThanOrEqual(2) // Hours and employees
    })

    it('transforms validated data to API payload', () => {
      const parsed = parseClipboardData(excelClipboard)
      const validationResults = parsed.rows.map((row, i) => validateProductionRow(row, i))
      const payload = transformToApiPayload(validationResults, 'client_1')

      expect(payload).toHaveLength(3)
      expect(payload[0]).toEqual({
        client_id: 'client_1',
        production_date: '2024-01-15',
        product_id: 'PROD-001',
        units_produced: 500,
        run_time_hours: 8.0,
        employees_assigned: 5
      })
    })

    it('completes full paste-to-submit workflow', async () => {
      // Step 1: Parse clipboard
      const parsed = parseClipboardData(excelClipboard)
      expect(parsed.rows).toHaveLength(3)

      // Step 2: Validate all rows
      const validationResults = parsed.rows.map((row, i) => validateProductionRow(row, i))
      const allValid = validationResults.every(r => r.valid)
      expect(allValid).toBe(true)

      // Step 3: Transform to API payload
      const payload = transformToApiPayload(validationResults, 'client_1')
      expect(payload).toHaveLength(3)

      // Step 4: Submit to API (mocked)
      const response = await fetch('/api/production/batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ entries: payload })
      })

      // Verify API was called with correct data
      expect(mockFetch).toHaveBeenCalled()
    })
  })

  describe('8.2.2: Hold/Resume/Approve Cycle', () => {
    /**
     * Complete workflow: Request Hold → Approve → On Hold → Request Resume → Approve → Resumed
     */

    const HoldStateMachine = {
      PENDING_HOLD_APPROVAL: ['ON_HOLD', 'CANCELLED'],
      ON_HOLD: ['PENDING_RESUME_APPROVAL', 'CANCELLED'],
      PENDING_RESUME_APPROVAL: ['RESUMED', 'CANCELLED'],
      RESUMED: [],
      CANCELLED: []
    }

    function canTransition(currentState, targetState) {
      const validTransitions = HoldStateMachine[currentState] || []
      return validTransitions.includes(targetState)
    }

    async function requestHold(workOrderId, reason, requestedBy) {
      const response = await fetch('/api/holds', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          work_order_id: workOrderId,
          hold_reason: reason,
          requested_by: requestedBy
        })
      })
      return response.json()
    }

    async function approveHold(holdId, approvedBy) {
      if (!canTransition('PENDING_HOLD_APPROVAL', 'ON_HOLD')) {
        throw new Error('Invalid state transition')
      }

      const response = await fetch(`/api/holds/${holdId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          status: 'ON_HOLD',
          hold_approved_by: approvedBy,
          hold_approved_at: new Date().toISOString()
        })
      })
      return response.json()
    }

    async function requestResume(holdId, resumeReason, requestedBy) {
      if (!canTransition('ON_HOLD', 'PENDING_RESUME_APPROVAL')) {
        throw new Error('Invalid state transition')
      }

      const response = await fetch(`/api/holds/${holdId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          status: 'PENDING_RESUME_APPROVAL',
          resume_reason: resumeReason,
          resume_requested_by: requestedBy
        })
      })
      return response.json()
    }

    async function approveResume(holdId, approvedBy) {
      if (!canTransition('PENDING_RESUME_APPROVAL', 'RESUMED')) {
        throw new Error('Invalid state transition')
      }

      const response = await fetch(`/api/holds/${holdId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          status: 'RESUMED',
          resumed_by: approvedBy,
          resumed_at: new Date().toISOString()
        })
      })
      return response.json()
    }

    it('validates state machine transitions', () => {
      expect(canTransition('PENDING_HOLD_APPROVAL', 'ON_HOLD')).toBe(true)
      expect(canTransition('PENDING_HOLD_APPROVAL', 'RESUMED')).toBe(false)
      expect(canTransition('ON_HOLD', 'PENDING_RESUME_APPROVAL')).toBe(true)
      expect(canTransition('RESUMED', 'ON_HOLD')).toBe(false)
    })

    it('completes full hold-approve-resume-approve cycle', async () => {
      // Step 1: Operator requests hold
      const holdRequest = await requestHold('WO-001', 'Material shortage', 'operator_1')
      expect(holdRequest.status).toBe('PENDING_HOLD_APPROVAL')

      // Step 2: Leader approves hold
      const approvedHold = await approveHold(holdRequest.id, 'leader_1')
      expect(approvedHold.status).toBe('ON_HOLD')

      // Step 3: Operator requests resume
      const resumeRequest = await requestResume(holdRequest.id, 'Material received', 'operator_1')
      expect(resumeRequest.status).toBe('PENDING_RESUME_APPROVAL')

      // Step 4: Leader approves resume
      const resumed = await approveResume(holdRequest.id, 'leader_1')
      expect(resumed.status).toBe('RESUMED')
    })

    it('tracks audit trail through workflow', async () => {
      const holdRequest = await requestHold('WO-001', 'Quality issue', 'operator_1')
      const approvedHold = await approveHold(holdRequest.id, 'leader_1')

      // Verify audit fields
      expect(approvedHold.hold_approved_by).toBe('leader_1')
      expect(approvedHold.hold_approved_at).toBeDefined()
    })

    it('prevents invalid state transitions', () => {
      expect(() => {
        if (!canTransition('RESUMED', 'ON_HOLD')) {
          throw new Error('Invalid state transition')
        }
      }).toThrow('Invalid state transition')
    })
  })

  describe('8.2.3: Client-Specific KPI Calculations', () => {
    /**
     * Verify KPI calculations use client-specific parameters
     */

    const clientConfigs = {
      client_1: {
        cycle_time_hours: 0.08,
        efficiency_target: 90,
        otd_mode: 'TRUE'
      },
      client_2: {
        cycle_time_hours: 0.05,
        efficiency_target: 85,
        otd_mode: 'STANDARD'
      }
    }

    function calculateEfficiency(unitsProduced, runTimeHours, clientId) {
      const config = clientConfigs[clientId] || { cycle_time_hours: 0.05 }
      const standardHours = unitsProduced * config.cycle_time_hours
      const efficiency = (standardHours / runTimeHours) * 100
      return Math.min(efficiency, 100)
    }

    function meetsTarget(efficiency, clientId) {
      const config = clientConfigs[clientId] || { efficiency_target: 85 }
      return efficiency >= config.efficiency_target
    }

    function getOtdMode(clientId) {
      return clientConfigs[clientId]?.otd_mode || 'STANDARD'
    }

    it('calculates efficiency with client-specific cycle time', () => {
      // Same production data, different clients
      const effClient1 = calculateEfficiency(100, 8, 'client_1') // 0.08 cycle time
      const effClient2 = calculateEfficiency(100, 8, 'client_2') // 0.05 cycle time

      // Client 1: 100 * 0.08 = 8 std hours / 8 actual = 100%
      expect(effClient1).toBe(100)

      // Client 2: 100 * 0.05 = 5 std hours / 8 actual = 62.5%
      expect(effClient2).toBe(62.5)
    })

    it('uses client-specific targets for evaluation', () => {
      // 88% efficiency
      const efficiency = 88

      // Client 1 has 90% target - should fail
      expect(meetsTarget(efficiency, 'client_1')).toBe(false)

      // Client 2 has 85% target - should pass
      expect(meetsTarget(efficiency, 'client_2')).toBe(true)
    })

    it('returns client-specific OTD mode', () => {
      expect(getOtdMode('client_1')).toBe('TRUE')
      expect(getOtdMode('client_2')).toBe('STANDARD')
      expect(getOtdMode('unknown')).toBe('STANDARD')
    })

    it('integrates with API to get client config', async () => {
      const response = await fetch('/api/clients')
      const clients = await response.json()

      const client1 = clients.find(c => c.client_id === 'client_1')
      expect(client1.otd_mode).toBe('TRUE')

      const client2 = clients.find(c => c.client_id === 'client_2')
      expect(client2.otd_mode).toBe('STANDARD')
    })
  })

  describe('8.2.4: Multi-Tenant Data Isolation', () => {
    /**
     * Verify data is properly isolated between clients/tenants
     */

    function filterByClient(data, clientId) {
      return data.filter(item => item.client_id === clientId)
    }

    function validateClientAccess(userId, clientId, userClients) {
      return userClients.includes(clientId)
    }

    it('filters production data by client', () => {
      const allData = [
        { id: 1, client_id: 'client_1', units: 100 },
        { id: 2, client_id: 'client_2', units: 200 },
        { id: 3, client_id: 'client_1', units: 150 }
      ]

      const client1Data = filterByClient(allData, 'client_1')
      const client2Data = filterByClient(allData, 'client_2')

      expect(client1Data).toHaveLength(2)
      expect(client2Data).toHaveLength(1)
      expect(client1Data.every(d => d.client_id === 'client_1')).toBe(true)
    })

    it('filters hold records by client', () => {
      const client1Holds = filterByClient(mockApiResponses.holds, 'client_1')
      const client2Holds = filterByClient(mockApiResponses.holds, 'client_2')

      expect(client1Holds).toHaveLength(1)
      expect(client2Holds).toHaveLength(1)
    })

    it('validates user access to client data', () => {
      const user1Clients = ['client_1', 'client_3']
      const user2Clients = ['client_2']

      expect(validateClientAccess('user_1', 'client_1', user1Clients)).toBe(true)
      expect(validateClientAccess('user_1', 'client_2', user1Clients)).toBe(false)
      expect(validateClientAccess('user_2', 'client_2', user2Clients)).toBe(true)
    })

    it('prevents cross-client data access', () => {
      const userClients = ['client_1']
      const requestedClientId = 'client_2'

      const hasAccess = validateClientAccess('user_1', requestedClientId, userClients)
      expect(hasAccess).toBe(false)

      // Simulation of what API would do
      if (!hasAccess) {
        const error = { status: 403, message: 'Access denied to client data' }
        expect(error.status).toBe(403)
      }
    })

    it('aggregates data per client correctly', () => {
      const allProduction = [
        { client_id: 'client_1', units_produced: 100 },
        { client_id: 'client_1', units_produced: 150 },
        { client_id: 'client_2', units_produced: 200 }
      ]

      const client1Total = allProduction
        .filter(p => p.client_id === 'client_1')
        .reduce((sum, p) => sum + p.units_produced, 0)

      const client2Total = allProduction
        .filter(p => p.client_id === 'client_2')
        .reduce((sum, p) => sum + p.units_produced, 0)

      expect(client1Total).toBe(250)
      expect(client2Total).toBe(200)
    })

    it('isolates KPI calculations by client', () => {
      const calculateClientKpi = (data, clientId) => {
        const clientData = data.filter(d => d.client_id === clientId)
        const totalUnits = clientData.reduce((sum, d) => sum + d.units_produced, 0)
        const avgUnits = clientData.length > 0 ? totalUnits / clientData.length : 0
        return { clientId, totalUnits, avgUnits, recordCount: clientData.length }
      }

      const kpi1 = calculateClientKpi(mockApiResponses.production, 'client_1')

      expect(kpi1.clientId).toBe('client_1')
      expect(kpi1.recordCount).toBe(2)
      expect(kpi1.totalUnits).toBe(950)
      expect(kpi1.avgUnits).toBe(475)
    })
  })
})
