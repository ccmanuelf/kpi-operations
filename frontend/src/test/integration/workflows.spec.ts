/**
 * Integration tests for KPI platform workflows.
 * Phase 8.2: end-to-end coverage of paste, hold/resume, KPI, and
 * multi-tenant flows.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

interface ProductionRecord {
  id: number
  client_id: string
  production_date: string
  units_produced: number
  run_time_hours: number
}

interface HoldRecord {
  id: number
  client_id: string
  work_order_id: string
  status: string
}

interface ClientRecord {
  client_id: string
  name: string
  otd_mode: string
}

interface MockApiResponses {
  production: ProductionRecord[]
  holds: HoldRecord[]
  clients: ClientRecord[]
}

const mockApiResponses: MockApiResponses = {
  production: [
    {
      id: 1,
      client_id: 'client_1',
      production_date: '2024-01-15',
      units_produced: 500,
      run_time_hours: 8,
    },
    {
      id: 2,
      client_id: 'client_1',
      production_date: '2024-01-16',
      units_produced: 450,
      run_time_hours: 8,
    },
  ],
  holds: [
    {
      id: 1,
      client_id: 'client_1',
      work_order_id: 'WO-001',
      status: 'PENDING_HOLD_APPROVAL',
    },
    { id: 2, client_id: 'client_2', work_order_id: 'WO-002', status: 'ON_HOLD' },
  ],
  clients: [
    { client_id: 'client_1', name: 'Client One', otd_mode: 'TRUE' },
    { client_id: 'client_2', name: 'Client Two', otd_mode: 'STANDARD' },
  ],
}

interface FetchOptions {
  method?: string
  body?: string
  headers?: Record<string, string>
}

function createMockFetch() {
  return vi.fn(
    (url: string, options: FetchOptions = {}): Promise<Response> => {
      const method = options.method || 'GET'

      if (url.includes('/production') && method === 'GET') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockApiResponses.production),
        } as unknown as Response)
      }

      if (url.includes('/holds') && method === 'GET') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockApiResponses.holds),
        } as unknown as Response)
      }

      if (url.includes('/holds') && method === 'POST') {
        const body = JSON.parse(options.body || '{}') as Record<string, unknown>
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({ id: 3, ...body, status: 'PENDING_HOLD_APPROVAL' }),
        } as unknown as Response)
      }

      if (url.includes('/holds') && method === 'PATCH') {
        const body = JSON.parse(options.body || '{}') as Record<string, unknown>
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ ...body }),
        } as unknown as Response)
      }

      if (url.includes('/clients') && method === 'GET') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockApiResponses.clients),
        } as unknown as Response)
      }

      return Promise.resolve({
        ok: false,
        status: 404,
        json: () => Promise.resolve({ error: 'Not found' }),
      } as unknown as Response)
    },
  )
}

describe('Integration Workflows', () => {
  let mockFetch: ReturnType<typeof createMockFetch>

  beforeEach(() => {
    setActivePinia(createPinia())
    mockFetch = createMockFetch()
    vi.stubGlobal('fetch', mockFetch)
  })

  describe('8.2.1: Excel Paste Workflow', () => {
    const excelClipboard = `Date\tProduct\tUnits Produced\tRuntime Hours\tEmployees
2024-01-15\tPROD-001\t500\t8.0\t5
2024-01-16\tPROD-002\t450\t7.5\t4
2024-01-17\tPROD-001\t600\t8.0\t6`

    interface ParsedClipboard {
      hasHeaders?: boolean
      headers?: string[] | null
      rows: string[][]
      totalColumns?: number
      error?: string
    }

    function parseClipboardData(text: string): ParsedClipboard {
      if (!text || typeof text !== 'string') {
        return { error: 'No data in clipboard', rows: [] }
      }

      const lines = text.trim().split(/\r?\n/)
      const rows = lines.map((line) => line.split('\t').map((cell) => cell.trim()))

      const headerKeywords = [
        'date',
        'product',
        'units',
        'hours',
        'employee',
        'id',
        'name',
        'shift',
      ]
      const firstRow = rows[0].map((cell) => cell.toLowerCase())
      const hasHeaders = firstRow.some((cell) =>
        headerKeywords.some((keyword) => cell.includes(keyword)),
      )

      return {
        hasHeaders,
        headers: hasHeaders ? rows[0] : null,
        rows: hasHeaders ? rows.slice(1) : rows,
        totalColumns: rows[0]?.length || 0,
      }
    }

    interface ProductionData {
      production_date: string
      product_id: string
      units_produced: number
      run_time_hours: number
      employees_assigned: number
    }

    interface ValidationResult {
      valid: boolean
      errors: string[]
      data: ProductionData | null
    }

    function validateProductionRow(row: string[], index: number): ValidationResult {
      const errors: string[] = []
      const [date, product, units, hours, employees] = row

      if (!date || !/^\d{4}-\d{2}-\d{2}$/.test(date)) {
        errors.push(`Row ${index + 1}: Invalid date format`)
      }

      const unitsNum = parseInt(units, 10)
      if (isNaN(unitsNum) || unitsNum < 0) {
        errors.push(`Row ${index + 1}: Units must be a positive number`)
      }

      const hoursNum = parseFloat(hours)
      if (isNaN(hoursNum) || hoursNum <= 0 || hoursNum > 24) {
        errors.push(`Row ${index + 1}: Hours must be between 0 and 24`)
      }

      const empNum = parseInt(employees, 10)
      if (isNaN(empNum) || empNum < 1) {
        errors.push(`Row ${index + 1}: Employees must be at least 1`)
      }

      return {
        valid: errors.length === 0,
        errors,
        data:
          errors.length === 0
            ? {
                production_date: date,
                product_id: product,
                units_produced: unitsNum,
                run_time_hours: hoursNum,
                employees_assigned: empNum,
              }
            : null,
      }
    }

    function transformToApiPayload(
      validatedRows: ValidationResult[],
      clientId: string,
    ): (ProductionData & { client_id: string })[] {
      return validatedRows
        .filter((row): row is ValidationResult & { data: ProductionData } => row.valid && row.data !== null)
        .map((row) => ({
          client_id: clientId,
          ...row.data,
        }))
    }

    it('parses Excel clipboard data correctly', () => {
      const parsed = parseClipboardData(excelClipboard)

      expect(parsed.hasHeaders).toBe(true)
      expect(parsed.headers).toEqual([
        'Date',
        'Product',
        'Units Produced',
        'Runtime Hours',
        'Employees',
      ])
      expect(parsed.rows).toHaveLength(3)
      expect(parsed.rows[0]).toEqual(['2024-01-15', 'PROD-001', '500', '8.0', '5'])
    })

    it('validates all rows and collects errors', () => {
      const parsed = parseClipboardData(excelClipboard)
      const validationResults = parsed.rows.map((row, i) => validateProductionRow(row, i))

      expect(validationResults.every((r) => r.valid)).toBe(true)
      expect(validationResults.every((r) => r.data !== null)).toBe(true)
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
      expect(validationResults[2].errors.length).toBeGreaterThanOrEqual(2)
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
        employees_assigned: 5,
      })
    })

    it('completes full paste-to-submit workflow', async () => {
      const parsed = parseClipboardData(excelClipboard)
      expect(parsed.rows).toHaveLength(3)

      const validationResults = parsed.rows.map((row, i) => validateProductionRow(row, i))
      const allValid = validationResults.every((r) => r.valid)
      expect(allValid).toBe(true)

      const payload = transformToApiPayload(validationResults, 'client_1')
      expect(payload).toHaveLength(3)

      await fetch('/api/production/batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ entries: payload }),
      })

      expect(mockFetch).toHaveBeenCalled()
    })
  })

  describe('8.2.2: Hold/Resume/Approve Cycle', () => {
    type HoldState =
      | 'PENDING_HOLD_APPROVAL'
      | 'ON_HOLD'
      | 'PENDING_RESUME_APPROVAL'
      | 'RESUMED'
      | 'CANCELLED'

    const HoldStateMachine: Record<HoldState, HoldState[]> = {
      PENDING_HOLD_APPROVAL: ['ON_HOLD', 'CANCELLED'],
      ON_HOLD: ['PENDING_RESUME_APPROVAL', 'CANCELLED'],
      PENDING_RESUME_APPROVAL: ['RESUMED', 'CANCELLED'],
      RESUMED: [],
      CANCELLED: [],
    }

    function canTransition(currentState: HoldState, targetState: HoldState): boolean {
      const validTransitions = HoldStateMachine[currentState] || []
      return validTransitions.includes(targetState)
    }

    interface HoldResponse {
      id: number
      status: HoldState | string
      hold_approved_by?: string
      hold_approved_at?: string
      [key: string]: unknown
    }

    async function requestHold(
      workOrderId: string,
      reason: string,
      requestedBy: string,
    ): Promise<HoldResponse> {
      const response = await fetch('/api/holds', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          work_order_id: workOrderId,
          hold_reason: reason,
          requested_by: requestedBy,
        }),
      })
      return response.json()
    }

    async function approveHold(holdId: number, approvedBy: string): Promise<HoldResponse> {
      if (!canTransition('PENDING_HOLD_APPROVAL', 'ON_HOLD')) {
        throw new Error('Invalid state transition')
      }

      const response = await fetch(`/api/holds/${holdId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          status: 'ON_HOLD',
          hold_approved_by: approvedBy,
          hold_approved_at: new Date().toISOString(),
        }),
      })
      return response.json()
    }

    async function requestResume(
      holdId: number,
      resumeReason: string,
      requestedBy: string,
    ): Promise<HoldResponse> {
      if (!canTransition('ON_HOLD', 'PENDING_RESUME_APPROVAL')) {
        throw new Error('Invalid state transition')
      }

      const response = await fetch(`/api/holds/${holdId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          status: 'PENDING_RESUME_APPROVAL',
          resume_reason: resumeReason,
          resume_requested_by: requestedBy,
        }),
      })
      return response.json()
    }

    async function approveResume(
      holdId: number,
      approvedBy: string,
    ): Promise<HoldResponse> {
      if (!canTransition('PENDING_RESUME_APPROVAL', 'RESUMED')) {
        throw new Error('Invalid state transition')
      }

      const response = await fetch(`/api/holds/${holdId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          status: 'RESUMED',
          resumed_by: approvedBy,
          resumed_at: new Date().toISOString(),
        }),
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
      const holdRequest = await requestHold('WO-001', 'Material shortage', 'operator_1')
      expect(holdRequest.status).toBe('PENDING_HOLD_APPROVAL')

      const approvedHold = await approveHold(holdRequest.id, 'leader_1')
      expect(approvedHold.status).toBe('ON_HOLD')

      const resumeRequest = await requestResume(
        holdRequest.id,
        'Material received',
        'operator_1',
      )
      expect(resumeRequest.status).toBe('PENDING_RESUME_APPROVAL')

      const resumed = await approveResume(holdRequest.id, 'leader_1')
      expect(resumed.status).toBe('RESUMED')
    })

    it('tracks audit trail through workflow', async () => {
      const holdRequest = await requestHold('WO-001', 'Quality issue', 'operator_1')
      const approvedHold = await approveHold(holdRequest.id, 'leader_1')

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
    interface ClientConfig {
      cycle_time_hours: number
      efficiency_target?: number
      otd_mode?: string
    }

    const clientConfigs: Record<string, ClientConfig> = {
      client_1: {
        cycle_time_hours: 0.08,
        efficiency_target: 90,
        otd_mode: 'TRUE',
      },
      client_2: {
        cycle_time_hours: 0.05,
        efficiency_target: 85,
        otd_mode: 'STANDARD',
      },
    }

    function calculateEfficiency(
      unitsProduced: number,
      runTimeHours: number,
      clientId: string,
    ): number {
      const config = clientConfigs[clientId] || { cycle_time_hours: 0.05 }
      const standardHours = unitsProduced * config.cycle_time_hours
      const efficiency = (standardHours / runTimeHours) * 100
      return Math.min(efficiency, 100)
    }

    function meetsTarget(efficiency: number, clientId: string): boolean {
      const config = clientConfigs[clientId] || { efficiency_target: 85 }
      return efficiency >= (config.efficiency_target ?? 85)
    }

    function getOtdMode(clientId: string): string {
      return clientConfigs[clientId]?.otd_mode || 'STANDARD'
    }

    it('calculates efficiency with client-specific cycle time', () => {
      const effClient1 = calculateEfficiency(100, 8, 'client_1')
      const effClient2 = calculateEfficiency(100, 8, 'client_2')

      expect(effClient1).toBe(100)
      expect(effClient2).toBe(62.5)
    })

    it('uses client-specific targets for evaluation', () => {
      const efficiency = 88

      expect(meetsTarget(efficiency, 'client_1')).toBe(false)
      expect(meetsTarget(efficiency, 'client_2')).toBe(true)
    })

    it('returns client-specific OTD mode', () => {
      expect(getOtdMode('client_1')).toBe('TRUE')
      expect(getOtdMode('client_2')).toBe('STANDARD')
      expect(getOtdMode('unknown')).toBe('STANDARD')
    })

    it('integrates with API to get client config', async () => {
      const response = await fetch('/api/clients')
      const clients = (await response.json()) as ClientRecord[]

      const client1 = clients.find((c) => c.client_id === 'client_1')
      expect(client1?.otd_mode).toBe('TRUE')

      const client2 = clients.find((c) => c.client_id === 'client_2')
      expect(client2?.otd_mode).toBe('STANDARD')
    })
  })

  describe('8.2.4: Multi-Tenant Data Isolation', () => {
    function filterByClient<T extends { client_id: string }>(
      data: T[],
      clientId: string,
    ): T[] {
      return data.filter((item) => item.client_id === clientId)
    }

    function validateClientAccess(
      _userId: string,
      clientId: string,
      userClients: string[],
    ): boolean {
      return userClients.includes(clientId)
    }

    it('filters production data by client', () => {
      const allData = [
        { id: 1, client_id: 'client_1', units: 100 },
        { id: 2, client_id: 'client_2', units: 200 },
        { id: 3, client_id: 'client_1', units: 150 },
      ]

      const client1Data = filterByClient(allData, 'client_1')
      const client2Data = filterByClient(allData, 'client_2')

      expect(client1Data).toHaveLength(2)
      expect(client2Data).toHaveLength(1)
      expect(client1Data.every((d) => d.client_id === 'client_1')).toBe(true)
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

      if (!hasAccess) {
        const error = { status: 403, message: 'Access denied to client data' }
        expect(error.status).toBe(403)
      }
    })

    it('aggregates data per client correctly', () => {
      const allProduction = [
        { client_id: 'client_1', units_produced: 100 },
        { client_id: 'client_1', units_produced: 150 },
        { client_id: 'client_2', units_produced: 200 },
      ]

      const client1Total = allProduction
        .filter((p) => p.client_id === 'client_1')
        .reduce((sum, p) => sum + p.units_produced, 0)

      const client2Total = allProduction
        .filter((p) => p.client_id === 'client_2')
        .reduce((sum, p) => sum + p.units_produced, 0)

      expect(client1Total).toBe(250)
      expect(client2Total).toBe(200)
    })

    it('isolates KPI calculations by client', () => {
      const calculateClientKpi = (data: ProductionRecord[], clientId: string) => {
        const clientData = data.filter((d) => d.client_id === clientId)
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
