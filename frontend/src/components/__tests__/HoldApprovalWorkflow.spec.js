/**
 * Unit tests for Hold Approval Workflow
 * Phase 8.1.3: Testing hold approval states, transitions, and validations
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

// Mock API endpoints
const mockFetch = vi.fn()
global.fetch = mockFetch

// Mock localStorage
const mockLocalStorage = {
  getItem: vi.fn().mockReturnValue('mock_token'),
  setItem: vi.fn(),
  removeItem: vi.fn()
}
Object.defineProperty(window, 'localStorage', { value: mockLocalStorage })

// Hold approval workflow state machine
const HoldApprovalStateMachine = {
  states: {
    PENDING_HOLD_APPROVAL: 'PENDING_HOLD_APPROVAL',
    ON_HOLD: 'ON_HOLD',
    PENDING_RESUME_APPROVAL: 'PENDING_RESUME_APPROVAL',
    RESUMED: 'RESUMED',
    CANCELLED: 'CANCELLED'
  },

  transitions: {
    PENDING_HOLD_APPROVAL: ['ON_HOLD', 'CANCELLED'],
    ON_HOLD: ['PENDING_RESUME_APPROVAL', 'CANCELLED'],
    PENDING_RESUME_APPROVAL: ['RESUMED', 'CANCELLED'],
    RESUMED: [], // Terminal state
    CANCELLED: [] // Terminal state
  },

  canTransition(fromState, toState) {
    return this.transitions[fromState]?.includes(toState) || false
  },

  getNextActions(currentState) {
    const actions = {
      PENDING_HOLD_APPROVAL: ['approveHold', 'cancelHold'],
      ON_HOLD: ['requestResume', 'cancelHold'],
      PENDING_RESUME_APPROVAL: ['approveResume', 'cancelResume'],
      RESUMED: [],
      CANCELLED: []
    }
    return actions[currentState] || []
  }
}

// Testable approval logic component
const HoldApprovalLogic = {
  data() {
    return {
      entries: [],
      approving: false,
      error: null,
      statusOptions: [
        { label: 'Pending Hold Approval', value: 'PENDING_HOLD_APPROVAL' },
        { label: 'On Hold', value: 'ON_HOLD' },
        { label: 'Pending Resume Approval', value: 'PENDING_RESUME_APPROVAL' },
        { label: 'Resumed', value: 'RESUMED' },
        { label: 'Cancelled', value: 'CANCELLED' }
      ]
    }
  },
  computed: {
    pendingHoldApprovals() {
      return this.entries.filter(e => e.hold_status === 'PENDING_HOLD_APPROVAL')
    },
    pendingResumeApprovals() {
      return this.entries.filter(e => e.hold_status === 'PENDING_RESUME_APPROVAL')
    },
    totalPendingApprovals() {
      return this.pendingHoldApprovals.length + this.pendingResumeApprovals.length
    },
    activeHolds() {
      return this.entries.filter(e => e.hold_status === 'ON_HOLD')
    },
    resumedHolds() {
      return this.entries.filter(e => e.hold_status === 'RESUMED')
    },
    cancelledHolds() {
      return this.entries.filter(e => e.hold_status === 'CANCELLED')
    }
  },
  methods: {
    canApproveHold(entry) {
      return entry.hold_status === 'PENDING_HOLD_APPROVAL'
    },
    canRequestResume(entry) {
      return entry.hold_status === 'ON_HOLD'
    },
    canApproveResume(entry) {
      return entry.hold_status === 'PENDING_RESUME_APPROVAL'
    },
    getAvailableActions(entry) {
      return HoldApprovalStateMachine.getNextActions(entry.hold_status)
    },
    isTerminalState(status) {
      return status === 'RESUMED' || status === 'CANCELLED'
    },
    async approveHold(holdId) {
      this.approving = true
      this.error = null
      try {
        const response = await fetch(`/api/holds/${holdId}/approve-hold`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('access_token')}`
          }
        })
        if (!response.ok) {
          const errorData = await response.json()
          throw new Error(errorData.detail || 'Failed to approve hold')
        }
        return { success: true }
      } catch (error) {
        this.error = error.message
        return { success: false, error: error.message }
      } finally {
        this.approving = false
      }
    },
    async requestResume(holdId) {
      this.approving = true
      this.error = null
      try {
        const response = await fetch(`/api/holds/${holdId}/request-resume`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('access_token')}`
          }
        })
        if (!response.ok) {
          const errorData = await response.json()
          throw new Error(errorData.detail || 'Failed to request resume')
        }
        return { success: true }
      } catch (error) {
        this.error = error.message
        return { success: false, error: error.message }
      } finally {
        this.approving = false
      }
    },
    async approveResume(holdId) {
      this.approving = true
      this.error = null
      try {
        const response = await fetch(`/api/holds/${holdId}/approve-resume`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('access_token')}`
          }
        })
        if (!response.ok) {
          const errorData = await response.json()
          throw new Error(errorData.detail || 'Failed to approve resume')
        }
        return { success: true }
      } catch (error) {
        this.error = error.message
        return { success: false, error: error.message }
      } finally {
        this.approving = false
      }
    }
  },
  template: '<div></div>'
}

describe('Hold Approval Workflow', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockFetch.mockReset()
    global.confirm = vi.fn().mockReturnValue(true)
  })

  describe('State Machine Transitions', () => {
    it('allows PENDING_HOLD_APPROVAL to transition to ON_HOLD', () => {
      expect(HoldApprovalStateMachine.canTransition('PENDING_HOLD_APPROVAL', 'ON_HOLD')).toBe(true)
    })

    it('allows PENDING_HOLD_APPROVAL to transition to CANCELLED', () => {
      expect(HoldApprovalStateMachine.canTransition('PENDING_HOLD_APPROVAL', 'CANCELLED')).toBe(true)
    })

    it('allows ON_HOLD to transition to PENDING_RESUME_APPROVAL', () => {
      expect(HoldApprovalStateMachine.canTransition('ON_HOLD', 'PENDING_RESUME_APPROVAL')).toBe(true)
    })

    it('allows PENDING_RESUME_APPROVAL to transition to RESUMED', () => {
      expect(HoldApprovalStateMachine.canTransition('PENDING_RESUME_APPROVAL', 'RESUMED')).toBe(true)
    })

    it('prevents invalid transitions from RESUMED', () => {
      expect(HoldApprovalStateMachine.canTransition('RESUMED', 'ON_HOLD')).toBe(false)
      expect(HoldApprovalStateMachine.canTransition('RESUMED', 'PENDING_HOLD_APPROVAL')).toBe(false)
    })

    it('prevents invalid transitions from CANCELLED', () => {
      expect(HoldApprovalStateMachine.canTransition('CANCELLED', 'ON_HOLD')).toBe(false)
    })

    it('prevents skipping workflow steps', () => {
      // Cannot go directly from PENDING_HOLD_APPROVAL to RESUMED
      expect(HoldApprovalStateMachine.canTransition('PENDING_HOLD_APPROVAL', 'RESUMED')).toBe(false)

      // Cannot go directly from ON_HOLD to RESUMED
      expect(HoldApprovalStateMachine.canTransition('ON_HOLD', 'RESUMED')).toBe(false)
    })
  })

  describe('Available Actions', () => {
    it('returns correct actions for PENDING_HOLD_APPROVAL', () => {
      const actions = HoldApprovalStateMachine.getNextActions('PENDING_HOLD_APPROVAL')
      expect(actions).toContain('approveHold')
      expect(actions).toContain('cancelHold')
    })

    it('returns correct actions for ON_HOLD', () => {
      const actions = HoldApprovalStateMachine.getNextActions('ON_HOLD')
      expect(actions).toContain('requestResume')
      expect(actions).toContain('cancelHold')
    })

    it('returns correct actions for PENDING_RESUME_APPROVAL', () => {
      const actions = HoldApprovalStateMachine.getNextActions('PENDING_RESUME_APPROVAL')
      expect(actions).toContain('approveResume')
      expect(actions).toContain('cancelResume')
    })

    it('returns no actions for terminal states', () => {
      expect(HoldApprovalStateMachine.getNextActions('RESUMED')).toHaveLength(0)
      expect(HoldApprovalStateMachine.getNextActions('CANCELLED')).toHaveLength(0)
    })
  })

  describe('Entry Filtering by Status', () => {
    it('filters pending hold approvals correctly', () => {
      const wrapper = shallowMount(HoldApprovalLogic)
      wrapper.vm.entries = [
        { hold_id: 1, hold_status: 'PENDING_HOLD_APPROVAL' },
        { hold_id: 2, hold_status: 'ON_HOLD' },
        { hold_id: 3, hold_status: 'PENDING_HOLD_APPROVAL' }
      ]

      expect(wrapper.vm.pendingHoldApprovals).toHaveLength(2)
      expect(wrapper.vm.pendingHoldApprovals.map(e => e.hold_id)).toEqual([1, 3])
    })

    it('filters pending resume approvals correctly', () => {
      const wrapper = shallowMount(HoldApprovalLogic)
      wrapper.vm.entries = [
        { hold_id: 1, hold_status: 'PENDING_RESUME_APPROVAL' },
        { hold_id: 2, hold_status: 'ON_HOLD' },
        { hold_id: 3, hold_status: 'PENDING_RESUME_APPROVAL' }
      ]

      expect(wrapper.vm.pendingResumeApprovals).toHaveLength(2)
    })

    it('calculates total pending approvals', () => {
      const wrapper = shallowMount(HoldApprovalLogic)
      wrapper.vm.entries = [
        { hold_id: 1, hold_status: 'PENDING_HOLD_APPROVAL' },
        { hold_id: 2, hold_status: 'PENDING_RESUME_APPROVAL' },
        { hold_id: 3, hold_status: 'ON_HOLD' }
      ]

      expect(wrapper.vm.totalPendingApprovals).toBe(2)
    })

    it('filters active holds', () => {
      const wrapper = shallowMount(HoldApprovalLogic)
      wrapper.vm.entries = [
        { hold_id: 1, hold_status: 'ON_HOLD' },
        { hold_id: 2, hold_status: 'ON_HOLD' },
        { hold_id: 3, hold_status: 'RESUMED' }
      ]

      expect(wrapper.vm.activeHolds).toHaveLength(2)
    })

    it('filters resumed holds', () => {
      const wrapper = shallowMount(HoldApprovalLogic)
      wrapper.vm.entries = [
        { hold_id: 1, hold_status: 'RESUMED' },
        { hold_id: 2, hold_status: 'ON_HOLD' },
        { hold_id: 3, hold_status: 'RESUMED' }
      ]

      expect(wrapper.vm.resumedHolds).toHaveLength(2)
    })
  })

  describe('Action Permissions', () => {
    it('allows approve hold only for PENDING_HOLD_APPROVAL', () => {
      const wrapper = shallowMount(HoldApprovalLogic)

      expect(wrapper.vm.canApproveHold({ hold_status: 'PENDING_HOLD_APPROVAL' })).toBe(true)
      expect(wrapper.vm.canApproveHold({ hold_status: 'ON_HOLD' })).toBe(false)
      expect(wrapper.vm.canApproveHold({ hold_status: 'RESUMED' })).toBe(false)
    })

    it('allows request resume only for ON_HOLD', () => {
      const wrapper = shallowMount(HoldApprovalLogic)

      expect(wrapper.vm.canRequestResume({ hold_status: 'ON_HOLD' })).toBe(true)
      expect(wrapper.vm.canRequestResume({ hold_status: 'PENDING_HOLD_APPROVAL' })).toBe(false)
      expect(wrapper.vm.canRequestResume({ hold_status: 'RESUMED' })).toBe(false)
    })

    it('allows approve resume only for PENDING_RESUME_APPROVAL', () => {
      const wrapper = shallowMount(HoldApprovalLogic)

      expect(wrapper.vm.canApproveResume({ hold_status: 'PENDING_RESUME_APPROVAL' })).toBe(true)
      expect(wrapper.vm.canApproveResume({ hold_status: 'ON_HOLD' })).toBe(false)
      expect(wrapper.vm.canApproveResume({ hold_status: 'RESUMED' })).toBe(false)
    })

    it('identifies terminal states', () => {
      const wrapper = shallowMount(HoldApprovalLogic)

      expect(wrapper.vm.isTerminalState('RESUMED')).toBe(true)
      expect(wrapper.vm.isTerminalState('CANCELLED')).toBe(true)
      expect(wrapper.vm.isTerminalState('ON_HOLD')).toBe(false)
      expect(wrapper.vm.isTerminalState('PENDING_HOLD_APPROVAL')).toBe(false)
    })
  })

  describe('API Integration: Approve Hold', () => {
    it('successfully approves hold', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true, hold_status: 'ON_HOLD' })
      })

      const wrapper = shallowMount(HoldApprovalLogic)
      const result = await wrapper.vm.approveHold(123)

      expect(result.success).toBe(true)
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/holds/123/approve-hold',
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'Authorization': 'Bearer mock_token'
          })
        })
      )
    })

    it('handles approval failure', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        json: async () => ({ detail: 'Insufficient permissions' })
      })

      const wrapper = shallowMount(HoldApprovalLogic)
      const result = await wrapper.vm.approveHold(123)

      expect(result.success).toBe(false)
      expect(result.error).toBe('Insufficient permissions')
      expect(wrapper.vm.error).toBe('Insufficient permissions')
    })

    it('sets approving state during request', async () => {
      let resolvePromise
      mockFetch.mockReturnValueOnce(new Promise(resolve => {
        resolvePromise = resolve
      }))

      const wrapper = shallowMount(HoldApprovalLogic)
      const promise = wrapper.vm.approveHold(123)

      expect(wrapper.vm.approving).toBe(true)

      resolvePromise({
        ok: true,
        json: async () => ({ success: true })
      })

      await promise
      expect(wrapper.vm.approving).toBe(false)
    })
  })

  describe('API Integration: Request Resume', () => {
    it('successfully requests resume', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true, hold_status: 'PENDING_RESUME_APPROVAL' })
      })

      const wrapper = shallowMount(HoldApprovalLogic)
      const result = await wrapper.vm.requestResume(123)

      expect(result.success).toBe(true)
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/holds/123/request-resume',
        expect.objectContaining({ method: 'POST' })
      )
    })

    it('handles request resume failure', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        json: async () => ({ detail: 'Hold not in correct state' })
      })

      const wrapper = shallowMount(HoldApprovalLogic)
      const result = await wrapper.vm.requestResume(123)

      expect(result.success).toBe(false)
      expect(result.error).toBe('Hold not in correct state')
    })
  })

  describe('API Integration: Approve Resume', () => {
    it('successfully approves resume', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true, hold_status: 'RESUMED' })
      })

      const wrapper = shallowMount(HoldApprovalLogic)
      const result = await wrapper.vm.approveResume(123)

      expect(result.success).toBe(true)
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/holds/123/approve-resume',
        expect.objectContaining({ method: 'POST' })
      )
    })

    it('handles approve resume failure', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        json: async () => ({ detail: 'Resume already approved' })
      })

      const wrapper = shallowMount(HoldApprovalLogic)
      const result = await wrapper.vm.approveResume(123)

      expect(result.success).toBe(false)
      expect(result.error).toBe('Resume already approved')
    })
  })

  describe('Status Options', () => {
    it('provides all status options', () => {
      const wrapper = shallowMount(HoldApprovalLogic)

      expect(wrapper.vm.statusOptions).toHaveLength(5)
      expect(wrapper.vm.statusOptions.map(o => o.value)).toContain('PENDING_HOLD_APPROVAL')
      expect(wrapper.vm.statusOptions.map(o => o.value)).toContain('ON_HOLD')
      expect(wrapper.vm.statusOptions.map(o => o.value)).toContain('PENDING_RESUME_APPROVAL')
      expect(wrapper.vm.statusOptions.map(o => o.value)).toContain('RESUMED')
      expect(wrapper.vm.statusOptions.map(o => o.value)).toContain('CANCELLED')
    })
  })

  describe('Complete Workflow Scenario', () => {
    it('handles full approval workflow', async () => {
      const wrapper = shallowMount(HoldApprovalLogic)

      // Step 1: Pending hold approval
      let entry = { hold_id: 1, hold_status: 'PENDING_HOLD_APPROVAL' }
      expect(wrapper.vm.canApproveHold(entry)).toBe(true)
      expect(wrapper.vm.canRequestResume(entry)).toBe(false)

      // Step 2: Approve hold -> ON_HOLD
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ hold_status: 'ON_HOLD' })
      })
      await wrapper.vm.approveHold(1)
      entry.hold_status = 'ON_HOLD'

      expect(wrapper.vm.canApproveHold(entry)).toBe(false)
      expect(wrapper.vm.canRequestResume(entry)).toBe(true)

      // Step 3: Request resume -> PENDING_RESUME_APPROVAL
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ hold_status: 'PENDING_RESUME_APPROVAL' })
      })
      await wrapper.vm.requestResume(1)
      entry.hold_status = 'PENDING_RESUME_APPROVAL'

      expect(wrapper.vm.canRequestResume(entry)).toBe(false)
      expect(wrapper.vm.canApproveResume(entry)).toBe(true)

      // Step 4: Approve resume -> RESUMED
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ hold_status: 'RESUMED' })
      })
      await wrapper.vm.approveResume(1)
      entry.hold_status = 'RESUMED'

      expect(wrapper.vm.isTerminalState(entry.hold_status)).toBe(true)
      expect(wrapper.vm.getAvailableActions(entry)).toHaveLength(0)
    })
  })
})

describe('Hold Entry Grid Approval Integration', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  describe('Pending Approvals Count', () => {
    it('calculates pending hold approvals count', () => {
      const wrapper = shallowMount(HoldApprovalLogic)
      wrapper.vm.entries = [
        { hold_status: 'PENDING_HOLD_APPROVAL' },
        { hold_status: 'PENDING_HOLD_APPROVAL' },
        { hold_status: 'ON_HOLD' }
      ]

      expect(wrapper.vm.pendingHoldApprovals.length).toBe(2)
    })

    it('calculates pending resume approvals count', () => {
      const wrapper = shallowMount(HoldApprovalLogic)
      wrapper.vm.entries = [
        { hold_status: 'PENDING_RESUME_APPROVAL' },
        { hold_status: 'ON_HOLD' },
        { hold_status: 'PENDING_RESUME_APPROVAL' }
      ]

      expect(wrapper.vm.pendingResumeApprovals.length).toBe(2)
    })

    it('calculates total pending correctly', () => {
      const wrapper = shallowMount(HoldApprovalLogic)
      wrapper.vm.entries = [
        { hold_status: 'PENDING_HOLD_APPROVAL' },
        { hold_status: 'PENDING_RESUME_APPROVAL' },
        { hold_status: 'ON_HOLD' },
        { hold_status: 'RESUMED' }
      ]

      expect(wrapper.vm.totalPendingApprovals).toBe(2)
    })
  })
})
