/**
 * Unit tests for Floating Pool Management
 * Phase 8.1.4: Testing floating pool assignment, double-assignment prevention, and status tracking
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

// Mock API
const mockApiGet = vi.fn()
const mockApiPost = vi.fn()

vi.mock('@/services/api', () => ({
  default: {
    get: (...args) => mockApiGet(...args),
    post: (...args) => mockApiPost(...args)
  }
}))

// Testable floating pool logic
const FloatingPoolLogic = {
  data() {
    return {
      loading: false,
      assigning: false,
      unassigning: null,
      entries: [],
      clients: [],
      statusFilter: null,
      clientFilter: null,
      assignDialog: {
        show: false,
        pool_id: null,
        employee_id: null,
        client_id: null,
        available_from: null,
        available_to: null,
        notes: '',
        error: null
      }
    }
  },
  computed: {
    summary() {
      const total = this.entries.length
      const assigned = this.entries.filter(e => e.current_assignment).length
      return {
        total,
        available: total - assigned,
        assigned
      }
    },
    utilizationPercent() {
      if (this.summary.total === 0) return 0
      return Math.round((this.summary.assigned / this.summary.total) * 100)
    },
    availableEmployees() {
      return this.entries.filter(e => !e.current_assignment).map(e => ({
        employee_id: e.employee_id,
        employee_name: e.employee_name || `Employee #${e.employee_id}`
      }))
    },
    assignedEmployees() {
      return this.entries.filter(e => e.current_assignment)
    },
    filteredEntries() {
      let result = [...this.entries]

      if (this.statusFilter === 'available') {
        result = result.filter(e => !e.current_assignment)
      } else if (this.statusFilter === 'assigned') {
        result = result.filter(e => e.current_assignment)
      }

      if (this.clientFilter) {
        result = result.filter(e => e.current_assignment === this.clientFilter)
      }

      return result
    }
  },
  methods: {
    isEmployeeAvailable(employeeId) {
      const employee = this.entries.find(e => e.employee_id === employeeId)
      return employee && !employee.current_assignment
    },
    isAlreadyAssigned(employeeId) {
      const employee = this.entries.find(e => e.employee_id === employeeId)
      return employee && !!employee.current_assignment
    },
    getEmployeeAssignment(employeeId) {
      const employee = this.entries.find(e => e.employee_id === employeeId)
      return employee?.current_assignment || null
    },
    validateAssignment(employeeId, clientId) {
      const errors = []

      if (!employeeId) {
        errors.push('Employee is required')
      }
      if (!clientId) {
        errors.push('Client is required')
      }

      // Check for double assignment
      if (employeeId && this.isAlreadyAssigned(employeeId)) {
        const currentClient = this.getEmployeeAssignment(employeeId)
        errors.push(`Employee is already assigned to client ${currentClient}`)
      }

      return {
        isValid: errors.length === 0,
        errors
      }
    },
    checkDoubleAssignment(employeeId, newClientId) {
      const currentAssignment = this.getEmployeeAssignment(employeeId)
      if (currentAssignment && currentAssignment !== newClientId) {
        return {
          hasConflict: true,
          currentClient: currentAssignment,
          newClient: newClientId,
          message: `Cannot assign employee to ${newClientId}. Already assigned to ${currentAssignment}.`
        }
      }
      return { hasConflict: false }
    },
    async assignEmployee(employeeId, clientId, options = {}) {
      // Validate first
      const validation = this.validateAssignment(employeeId, clientId)
      if (!validation.isValid) {
        return { success: false, errors: validation.errors }
      }

      // Check double assignment
      const doubleCheck = this.checkDoubleAssignment(employeeId, clientId)
      if (doubleCheck.hasConflict) {
        return { success: false, error: doubleCheck.message }
      }

      this.assigning = true
      try {
        const response = await mockApiPost('/api/floating-pool/assign', {
          employee_id: employeeId,
          client_id: clientId,
          available_from: options.available_from || null,
          available_to: options.available_to || null,
          notes: options.notes || null
        })

        return { success: true, data: response.data }
      } catch (error) {
        const message = error.response?.data?.detail || error.message
        return { success: false, error: message }
      } finally {
        this.assigning = false
      }
    },
    async unassignEmployee(poolId) {
      this.unassigning = poolId
      try {
        const response = await mockApiPost('/api/floating-pool/unassign', {
          pool_id: poolId
        })
        return { success: true, data: response.data }
      } catch (error) {
        return { success: false, error: error.message }
      } finally {
        this.unassigning = null
      }
    },
    getClientName(clientId) {
      const client = this.clients.find(c => c.client_id === clientId)
      return client?.name || clientId
    }
  },
  template: '<div></div>'
}

describe('Floating Pool Management', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  describe('Summary Calculations', () => {
    it('calculates total employees correctly', () => {
      const wrapper = shallowMount(FloatingPoolLogic)
      wrapper.vm.entries = [
        { employee_id: 1, current_assignment: null },
        { employee_id: 2, current_assignment: 'client_1' },
        { employee_id: 3, current_assignment: null }
      ]

      expect(wrapper.vm.summary.total).toBe(3)
    })

    it('calculates available employees correctly', () => {
      const wrapper = shallowMount(FloatingPoolLogic)
      wrapper.vm.entries = [
        { employee_id: 1, current_assignment: null },
        { employee_id: 2, current_assignment: 'client_1' },
        { employee_id: 3, current_assignment: null }
      ]

      expect(wrapper.vm.summary.available).toBe(2)
    })

    it('calculates assigned employees correctly', () => {
      const wrapper = shallowMount(FloatingPoolLogic)
      wrapper.vm.entries = [
        { employee_id: 1, current_assignment: 'client_1' },
        { employee_id: 2, current_assignment: 'client_2' },
        { employee_id: 3, current_assignment: null }
      ]

      expect(wrapper.vm.summary.assigned).toBe(2)
    })

    it('calculates utilization percentage', () => {
      const wrapper = shallowMount(FloatingPoolLogic)
      wrapper.vm.entries = [
        { employee_id: 1, current_assignment: 'client_1' },
        { employee_id: 2, current_assignment: 'client_2' },
        { employee_id: 3, current_assignment: null },
        { employee_id: 4, current_assignment: null }
      ]

      expect(wrapper.vm.utilizationPercent).toBe(50)
    })

    it('handles zero employees gracefully', () => {
      const wrapper = shallowMount(FloatingPoolLogic)
      wrapper.vm.entries = []

      expect(wrapper.vm.summary.total).toBe(0)
      expect(wrapper.vm.utilizationPercent).toBe(0)
    })
  })

  describe('Employee Availability', () => {
    it('identifies available employees', () => {
      const wrapper = shallowMount(FloatingPoolLogic)
      wrapper.vm.entries = [
        { employee_id: 1, current_assignment: null },
        { employee_id: 2, current_assignment: 'client_1' }
      ]

      expect(wrapper.vm.isEmployeeAvailable(1)).toBe(true)
      expect(wrapper.vm.isEmployeeAvailable(2)).toBe(false)
    })

    it('identifies assigned employees', () => {
      const wrapper = shallowMount(FloatingPoolLogic)
      wrapper.vm.entries = [
        { employee_id: 1, current_assignment: null },
        { employee_id: 2, current_assignment: 'client_1' }
      ]

      expect(wrapper.vm.isAlreadyAssigned(1)).toBe(false)
      expect(wrapper.vm.isAlreadyAssigned(2)).toBe(true)
    })

    it('returns list of available employees', () => {
      const wrapper = shallowMount(FloatingPoolLogic)
      wrapper.vm.entries = [
        { employee_id: 1, employee_name: 'John', current_assignment: null },
        { employee_id: 2, employee_name: 'Jane', current_assignment: 'client_1' },
        { employee_id: 3, employee_name: 'Bob', current_assignment: null }
      ]

      expect(wrapper.vm.availableEmployees).toHaveLength(2)
      expect(wrapper.vm.availableEmployees.map(e => e.employee_id)).toEqual([1, 3])
    })

    it('returns list of assigned employees', () => {
      const wrapper = shallowMount(FloatingPoolLogic)
      wrapper.vm.entries = [
        { employee_id: 1, current_assignment: null },
        { employee_id: 2, current_assignment: 'client_1' },
        { employee_id: 3, current_assignment: 'client_2' }
      ]

      expect(wrapper.vm.assignedEmployees).toHaveLength(2)
    })
  })

  describe('Double Assignment Prevention', () => {
    it('detects double assignment attempt', () => {
      const wrapper = shallowMount(FloatingPoolLogic)
      wrapper.vm.entries = [
        { employee_id: 1, current_assignment: 'client_1' }
      ]

      const result = wrapper.vm.checkDoubleAssignment(1, 'client_2')

      expect(result.hasConflict).toBe(true)
      expect(result.currentClient).toBe('client_1')
      expect(result.message).toContain('Already assigned')
    })

    it('allows reassignment to same client', () => {
      const wrapper = shallowMount(FloatingPoolLogic)
      wrapper.vm.entries = [
        { employee_id: 1, current_assignment: 'client_1' }
      ]

      const result = wrapper.vm.checkDoubleAssignment(1, 'client_1')

      expect(result.hasConflict).toBe(false)
    })

    it('allows assignment of available employee', () => {
      const wrapper = shallowMount(FloatingPoolLogic)
      wrapper.vm.entries = [
        { employee_id: 1, current_assignment: null }
      ]

      const result = wrapper.vm.checkDoubleAssignment(1, 'client_1')

      expect(result.hasConflict).toBe(false)
    })

    it('validates assignment with double assignment check', () => {
      const wrapper = shallowMount(FloatingPoolLogic)
      wrapper.vm.entries = [
        { employee_id: 1, current_assignment: 'client_1' }
      ]

      const validation = wrapper.vm.validateAssignment(1, 'client_2')

      expect(validation.isValid).toBe(false)
      expect(validation.errors.some(e => e.includes('already assigned'))).toBe(true)
    })
  })

  describe('Assignment Validation', () => {
    it('rejects assignment without employee', () => {
      const wrapper = shallowMount(FloatingPoolLogic)

      const validation = wrapper.vm.validateAssignment(null, 'client_1')

      expect(validation.isValid).toBe(false)
      expect(validation.errors).toContain('Employee is required')
    })

    it('rejects assignment without client', () => {
      const wrapper = shallowMount(FloatingPoolLogic)
      wrapper.vm.entries = [
        { employee_id: 1, current_assignment: null }
      ]

      const validation = wrapper.vm.validateAssignment(1, null)

      expect(validation.isValid).toBe(false)
      expect(validation.errors).toContain('Client is required')
    })

    it('accepts valid assignment', () => {
      const wrapper = shallowMount(FloatingPoolLogic)
      wrapper.vm.entries = [
        { employee_id: 1, current_assignment: null }
      ]

      const validation = wrapper.vm.validateAssignment(1, 'client_1')

      expect(validation.isValid).toBe(true)
      expect(validation.errors).toHaveLength(0)
    })
  })

  describe('API Integration: Assignment', () => {
    it('successfully assigns employee', async () => {
      mockApiPost.mockResolvedValueOnce({
        data: { pool_id: 1, employee_id: 1, current_assignment: 'client_1' }
      })

      const wrapper = shallowMount(FloatingPoolLogic)
      wrapper.vm.entries = [
        { employee_id: 1, current_assignment: null }
      ]

      const result = await wrapper.vm.assignEmployee(1, 'client_1')

      expect(result.success).toBe(true)
      expect(mockApiPost).toHaveBeenCalledWith(
        '/api/floating-pool/assign',
        expect.objectContaining({
          employee_id: 1,
          client_id: 'client_1'
        })
      )
    })

    it('prevents assignment of already assigned employee', async () => {
      const wrapper = shallowMount(FloatingPoolLogic)
      wrapper.vm.entries = [
        { employee_id: 1, current_assignment: 'client_1' }
      ]

      const result = await wrapper.vm.assignEmployee(1, 'client_2')

      expect(result.success).toBe(false)
      expect(mockApiPost).not.toHaveBeenCalled()
    })

    it('handles API error on assignment', async () => {
      mockApiPost.mockRejectedValueOnce({
        response: { data: { detail: 'Employee already assigned to another client' } }
      })

      const wrapper = shallowMount(FloatingPoolLogic)
      wrapper.vm.entries = [
        { employee_id: 1, current_assignment: null }
      ]

      const result = await wrapper.vm.assignEmployee(1, 'client_1')

      expect(result.success).toBe(false)
      expect(result.error).toBe('Employee already assigned to another client')
    })

    it('sets assigning state during request', async () => {
      let resolvePromise
      mockApiPost.mockReturnValueOnce(new Promise(resolve => {
        resolvePromise = resolve
      }))

      const wrapper = shallowMount(FloatingPoolLogic)
      wrapper.vm.entries = [
        { employee_id: 1, current_assignment: null }
      ]

      const promise = wrapper.vm.assignEmployee(1, 'client_1')

      expect(wrapper.vm.assigning).toBe(true)

      resolvePromise({ data: {} })
      await promise

      expect(wrapper.vm.assigning).toBe(false)
    })

    it('includes optional parameters in assignment', async () => {
      mockApiPost.mockResolvedValueOnce({ data: {} })

      const wrapper = shallowMount(FloatingPoolLogic)
      wrapper.vm.entries = [
        { employee_id: 1, current_assignment: null }
      ]

      await wrapper.vm.assignEmployee(1, 'client_1', {
        available_from: '2024-01-15T08:00',
        available_to: '2024-01-15T17:00',
        notes: 'Temporary assignment'
      })

      expect(mockApiPost).toHaveBeenCalledWith(
        '/api/floating-pool/assign',
        expect.objectContaining({
          available_from: '2024-01-15T08:00',
          available_to: '2024-01-15T17:00',
          notes: 'Temporary assignment'
        })
      )
    })
  })

  describe('API Integration: Unassignment', () => {
    it('successfully unassigns employee', async () => {
      mockApiPost.mockResolvedValueOnce({
        data: { pool_id: 1, current_assignment: null }
      })

      const wrapper = shallowMount(FloatingPoolLogic)
      const result = await wrapper.vm.unassignEmployee(1)

      expect(result.success).toBe(true)
      expect(mockApiPost).toHaveBeenCalledWith(
        '/api/floating-pool/unassign',
        { pool_id: 1 }
      )
    })

    it('handles unassignment failure', async () => {
      mockApiPost.mockRejectedValueOnce(new Error('Failed to unassign'))

      const wrapper = shallowMount(FloatingPoolLogic)
      const result = await wrapper.vm.unassignEmployee(1)

      expect(result.success).toBe(false)
      expect(result.error).toBe('Failed to unassign')
    })

    it('sets unassigning state with pool_id', async () => {
      let resolvePromise
      mockApiPost.mockReturnValueOnce(new Promise(resolve => {
        resolvePromise = resolve
      }))

      const wrapper = shallowMount(FloatingPoolLogic)
      const promise = wrapper.vm.unassignEmployee(5)

      expect(wrapper.vm.unassigning).toBe(5)

      resolvePromise({ data: {} })
      await promise

      expect(wrapper.vm.unassigning).toBe(null)
    })
  })

  describe('Filtering', () => {
    it('filters by available status', () => {
      const wrapper = shallowMount(FloatingPoolLogic)
      wrapper.vm.entries = [
        { employee_id: 1, current_assignment: null },
        { employee_id: 2, current_assignment: 'client_1' },
        { employee_id: 3, current_assignment: null }
      ]
      wrapper.vm.statusFilter = 'available'

      expect(wrapper.vm.filteredEntries).toHaveLength(2)
    })

    it('filters by assigned status', () => {
      const wrapper = shallowMount(FloatingPoolLogic)
      wrapper.vm.entries = [
        { employee_id: 1, current_assignment: null },
        { employee_id: 2, current_assignment: 'client_1' },
        { employee_id: 3, current_assignment: 'client_2' }
      ]
      wrapper.vm.statusFilter = 'assigned'

      expect(wrapper.vm.filteredEntries).toHaveLength(2)
    })

    it('filters by client', () => {
      const wrapper = shallowMount(FloatingPoolLogic)
      wrapper.vm.entries = [
        { employee_id: 1, current_assignment: 'client_1' },
        { employee_id: 2, current_assignment: 'client_2' },
        { employee_id: 3, current_assignment: 'client_1' }
      ]
      wrapper.vm.clientFilter = 'client_1'

      expect(wrapper.vm.filteredEntries).toHaveLength(2)
    })

    it('combines status and client filters', () => {
      const wrapper = shallowMount(FloatingPoolLogic)
      wrapper.vm.entries = [
        { employee_id: 1, current_assignment: 'client_1' },
        { employee_id: 2, current_assignment: 'client_2' },
        { employee_id: 3, current_assignment: null }
      ]
      wrapper.vm.statusFilter = 'assigned'
      wrapper.vm.clientFilter = 'client_1'

      expect(wrapper.vm.filteredEntries).toHaveLength(1)
      expect(wrapper.vm.filteredEntries[0].employee_id).toBe(1)
    })

    it('returns all entries when no filters applied', () => {
      const wrapper = shallowMount(FloatingPoolLogic)
      wrapper.vm.entries = [
        { employee_id: 1, current_assignment: 'client_1' },
        { employee_id: 2, current_assignment: null }
      ]
      wrapper.vm.statusFilter = null
      wrapper.vm.clientFilter = null

      expect(wrapper.vm.filteredEntries).toHaveLength(2)
    })
  })

  describe('Client Name Resolution', () => {
    it('resolves client name from ID', () => {
      const wrapper = shallowMount(FloatingPoolLogic)
      wrapper.vm.clients = [
        { client_id: 'client_1', name: 'Novalink Matamoros' },
        { client_id: 'client_2', name: 'Client B' }
      ]

      expect(wrapper.vm.getClientName('client_1')).toBe('Novalink Matamoros')
    })

    it('returns ID when client not found', () => {
      const wrapper = shallowMount(FloatingPoolLogic)
      wrapper.vm.clients = []

      expect(wrapper.vm.getClientName('unknown_client')).toBe('unknown_client')
    })
  })

  describe('Assignment Dialog State', () => {
    it('initializes with empty values', () => {
      const wrapper = shallowMount(FloatingPoolLogic)

      expect(wrapper.vm.assignDialog.show).toBe(false)
      expect(wrapper.vm.assignDialog.employee_id).toBeNull()
      expect(wrapper.vm.assignDialog.client_id).toBeNull()
      expect(wrapper.vm.assignDialog.error).toBeNull()
    })
  })
})

describe('Floating Pool Concurrent Assignment Prevention', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('prevents assigning same employee to multiple clients simultaneously', async () => {
    const wrapper = shallowMount(FloatingPoolLogic)
    wrapper.vm.entries = [
      { employee_id: 1, employee_name: 'John', current_assignment: 'client_1' }
    ]

    // First assignment to client_1 is already done
    // Now try to assign to client_2
    const result = await wrapper.vm.assignEmployee(1, 'client_2')

    expect(result.success).toBe(false)
    expect(result.error || result.errors?.join(',')).toContain('already assigned')
    expect(mockApiPost).not.toHaveBeenCalled()
  })

  it('allows assigning different employees to same client', async () => {
    mockApiPost.mockResolvedValue({ data: {} })

    const wrapper = shallowMount(FloatingPoolLogic)
    wrapper.vm.entries = [
      { employee_id: 1, employee_name: 'John', current_assignment: null },
      { employee_id: 2, employee_name: 'Jane', current_assignment: null }
    ]

    const result1 = await wrapper.vm.assignEmployee(1, 'client_1')
    const result2 = await wrapper.vm.assignEmployee(2, 'client_1')

    expect(result1.success).toBe(true)
    expect(result2.success).toBe(true)
    expect(mockApiPost).toHaveBeenCalledTimes(2)
  })

  it('provides clear error message for double assignment', () => {
    const wrapper = shallowMount(FloatingPoolLogic)
    wrapper.vm.entries = [
      { employee_id: 1, current_assignment: 'client_1' }
    ]

    const check = wrapper.vm.checkDoubleAssignment(1, 'client_2')

    expect(check.hasConflict).toBe(true)
    expect(check.message).toContain('client_2')
    expect(check.message).toContain('client_1')
  })
})
