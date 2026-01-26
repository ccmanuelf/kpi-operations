/**
 * Unit tests for Workflow Store
 * Phase 8: Increase test coverage
 */
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useWorkflowStore } from '../workflowStore'
import { useAuthStore } from '../authStore'

// Mock authStore
vi.mock('../authStore', () => ({
  useAuthStore: vi.fn(() => ({
    currentUser: { user_id: 'test-user' }
  }))
}))

// Mock API
vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn()
  }
}))

// Mock localStorage
const localStorageMock = {
  store: {},
  getItem: vi.fn((key) => localStorageMock.store[key] || null),
  setItem: vi.fn((key, value) => { localStorageMock.store[key] = value }),
  removeItem: vi.fn((key) => { delete localStorageMock.store[key] }),
  clear: vi.fn(() => { localStorageMock.store = {} })
}

describe('Workflow Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorageMock.clear()
    vi.stubGlobal('localStorage', localStorageMock)
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  describe('Initial State', () => {
    it('starts with no active workflow', () => {
      const store = useWorkflowStore()

      expect(store.currentWorkflow).toBeNull()
      expect(store.currentStep).toBe(0)
    })

    it('starts with empty completed steps', () => {
      const store = useWorkflowStore()

      expect(store.completedSteps).toEqual([])
      expect(store.skippedSteps).toEqual([])
    })

    it('starts with no active shift', () => {
      const store = useWorkflowStore()

      expect(store.activeShift).toBeNull()
      expect(store.hasActiveShift).toBe(false)
    })

    it('starts with no loading state', () => {
      const store = useWorkflowStore()

      expect(store.isLoading).toBe(false)
      expect(store.error).toBeNull()
    })
  })

  describe('Computed Properties', () => {
    it('returns empty steps when no workflow', () => {
      const store = useWorkflowStore()

      expect(store.workflowSteps).toEqual([])
      expect(store.totalSteps).toBe(0)
    })

    it('returns shift-start steps', () => {
      const store = useWorkflowStore()
      store.startWorkflow('shift-start')

      expect(store.workflowSteps.length).toBeGreaterThan(0)
      expect(store.workflowSteps[0].id).toBe('review-previous')
    })

    it('calculates isFirstStep correctly', () => {
      const store = useWorkflowStore()
      store.startWorkflow('shift-start')

      expect(store.isFirstStep).toBe(true)
    })

    it('calculates isLastStep correctly', () => {
      const store = useWorkflowStore()
      store.startWorkflow('shift-start')

      expect(store.isLastStep).toBe(false)
    })

    it('calculates progress', () => {
      const store = useWorkflowStore()
      store.startWorkflow('shift-start')

      expect(store.progress).toBe(0)
    })

    it('returns workflow title for shift-start', () => {
      const store = useWorkflowStore()
      store.startWorkflow('shift-start')

      expect(store.workflowTitle).toBe('Start Shift Workflow')
    })

    it('returns empty title when no workflow', () => {
      const store = useWorkflowStore()

      expect(store.workflowTitle).toBe('')
    })
  })

  describe('Start Workflow', () => {
    it('starts shift-start workflow', () => {
      const store = useWorkflowStore()

      const result = store.startWorkflow('shift-start')

      expect(result).toBe(true)
      expect(store.currentWorkflow).toBe('shift-start')
      expect(store.currentStep).toBe(0)
    })

    it('rejects invalid workflow type', () => {
      const store = useWorkflowStore()

      const result = store.startWorkflow('invalid')

      expect(result).toBe(false)
      expect(store.currentWorkflow).toBeNull()
    })

    it('prevents shift-end without active shift', () => {
      const store = useWorkflowStore()

      const result = store.startWorkflow('shift-end')

      expect(result).toBe(false)
      expect(store.error).toContain('No active shift')
    })

    it('prevents shift-start with existing active shift', () => {
      const store = useWorkflowStore()
      store.activeShift = { id: 1 } // Simulate active shift

      const result = store.startWorkflow('shift-start')

      expect(result).toBe(false)
      expect(store.error).toContain('already active')
    })

    it('clears previous state when starting', () => {
      const store = useWorkflowStore()
      store.completedSteps = ['step-1']
      store.workflowData = { test: true }

      store.startWorkflow('shift-start')

      expect(store.completedSteps).toEqual([])
      expect(store.workflowData).toEqual({})
    })

    it('saves to localStorage', () => {
      const store = useWorkflowStore()

      store.startWorkflow('shift-start')

      expect(localStorageMock.setItem).toHaveBeenCalled()
    })
  })

  describe('Cancel Workflow', () => {
    it('cancels active workflow', () => {
      const store = useWorkflowStore()
      store.startWorkflow('shift-start')

      store.cancelWorkflow()

      expect(store.currentWorkflow).toBeNull()
      expect(store.currentStep).toBe(0)
      expect(store.completedSteps).toEqual([])
    })

    it('clears error when canceling', () => {
      const store = useWorkflowStore()
      store.error = 'Some error'

      store.cancelWorkflow()

      expect(store.error).toBeNull()
    })
  })

  describe('Navigation', () => {
    it('moves to next step', () => {
      const store = useWorkflowStore()
      store.startWorkflow('shift-start')

      const result = store.nextStep()

      expect(result).toBe(true)
      expect(store.currentStep).toBe(1)
    })

    it('marks step as completed when moving next', () => {
      const store = useWorkflowStore()
      store.startWorkflow('shift-start')
      const firstStepId = store.workflowSteps[0].id

      store.nextStep()

      expect(store.completedSteps).toContain(firstStepId)
    })

    it('returns false at last step', () => {
      const store = useWorkflowStore()
      store.startWorkflow('shift-start')
      // Go to last step
      while (!store.isLastStep) {
        store.currentStep++
      }

      const result = store.nextStep()

      expect(result).toBe(false)
    })

    it('moves to previous step', () => {
      const store = useWorkflowStore()
      store.startWorkflow('shift-start')
      store.currentStep = 2

      const result = store.previousStep()

      expect(result).toBe(true)
      expect(store.currentStep).toBe(1)
    })

    it('returns false at first step', () => {
      const store = useWorkflowStore()
      store.startWorkflow('shift-start')

      const result = store.previousStep()

      expect(result).toBe(false)
    })

    it('goes to specific step', () => {
      const store = useWorkflowStore()
      store.startWorkflow('shift-start')
      // Complete first step
      store.completedSteps.push(store.workflowSteps[0].id)
      store.currentStep = 1

      const result = store.goToStep(0)

      expect(result).toBe(true)
      expect(store.currentStep).toBe(0)
    })

    it('rejects invalid step index', () => {
      const store = useWorkflowStore()
      store.startWorkflow('shift-start')

      expect(store.goToStep(-1)).toBe(false)
      expect(store.goToStep(999)).toBe(false)
    })
  })

  describe('Skip Step', () => {
    it('skips optional step', () => {
      const store = useWorkflowStore()
      store.startWorkflow('shift-start')
      // First step (review-previous) is optional

      const result = store.skipStep()

      expect(result).toBe(true)
      expect(store.skippedSteps).toContain('review-previous')
    })

    it('moves to next after skip', () => {
      const store = useWorkflowStore()
      store.startWorkflow('shift-start')
      const initialStep = store.currentStep

      store.skipStep()

      expect(store.currentStep).toBe(initialStep + 1)
    })
  })

  describe('Step Data', () => {
    it('updates step data', () => {
      const store = useWorkflowStore()
      store.startWorkflow('shift-start')

      store.updateStepData('review-previous', { reviewed: true, notes: 'All good' })

      expect(store.workflowData['review-previous']).toEqual({
        reviewed: true,
        notes: 'All good'
      })
    })

    it('completes step with data', () => {
      const store = useWorkflowStore()
      store.startWorkflow('shift-start')

      const result = store.completeStep('review-previous', { notes: 'Done' })

      expect(result).toBe(true)
      expect(store.completedSteps).toContain('review-previous')
      expect(store.workflowData['review-previous'].isValid).toBe(true)
    })

    it('checks if step is completed', () => {
      const store = useWorkflowStore()
      store.startWorkflow('shift-start')
      store.completedSteps.push('review-previous')

      expect(store.isStepCompleted('review-previous')).toBe(true)
      expect(store.isStepCompleted('other-step')).toBe(false)
    })

    it('checks if step is skipped', () => {
      const store = useWorkflowStore()
      store.startWorkflow('shift-start')
      store.skippedSteps.push('review-previous')

      expect(store.isStepSkipped('review-previous')).toBe(true)
      expect(store.isStepSkipped('other-step')).toBe(false)
    })

    it('gets step status', () => {
      const store = useWorkflowStore()
      store.startWorkflow('shift-start')

      expect(store.getStepStatus(0)).toBe('current')
      expect(store.getStepStatus(1)).toBe('pending')
    })
  })

  describe('canProceed', () => {
    it('returns false when no workflow', () => {
      const store = useWorkflowStore()

      expect(store.canProceed).toBe(false)
    })

    it('returns true for completed step', () => {
      const store = useWorkflowStore()
      store.startWorkflow('shift-start')
      store.completedSteps.push(store.workflowSteps[0].id)

      expect(store.canProceed).toBe(true)
    })

    it('returns true for skipped optional step', () => {
      const store = useWorkflowStore()
      store.startWorkflow('shift-start')
      store.skippedSteps.push(store.workflowSteps[0].id)

      expect(store.canProceed).toBe(true)
    })
  })

  describe('canSkip', () => {
    it('returns true for optional step', () => {
      const store = useWorkflowStore()
      store.startWorkflow('shift-start')
      // First step (review-previous) is optional

      expect(store.canSkip).toBe(true)
    })

    it('returns falsy when no workflow', () => {
      const store = useWorkflowStore()

      // canSkip depends on currentStepData which is null when no workflow
      expect(store.canSkip).toBeFalsy()
    })
  })

  describe('localStorage Persistence', () => {
    it('saves workflow state', () => {
      const store = useWorkflowStore()
      store.startWorkflow('shift-start')

      expect(localStorageMock.setItem).toHaveBeenCalledWith(
        'kpi-workflow-progress',
        expect.any(String)
      )
    })

    it('saves state on navigation', () => {
      const store = useWorkflowStore()
      store.startWorkflow('shift-start')
      localStorageMock.setItem.mockClear()

      store.nextStep()

      expect(localStorageMock.setItem).toHaveBeenCalled()
    })

    it('saves state on cancel', () => {
      const store = useWorkflowStore()
      store.startWorkflow('shift-start')
      localStorageMock.setItem.mockClear()

      store.cancelWorkflow()

      expect(localStorageMock.setItem).toHaveBeenCalled()
    })

    it('handles localStorage getItem errors', () => {
      // Test that store creation doesn't fail even with localStorage errors
      localStorageMock.getItem.mockImplementationOnce(() => {
        throw new Error('localStorage error')
      })

      // Should not throw - store handles errors gracefully
      expect(() => useWorkflowStore()).not.toThrow()
    })

    it('handles invalid JSON in localStorage', () => {
      localStorageMock.store['kpi-workflow-progress'] = 'invalid json'

      // Should not throw
      expect(() => useWorkflowStore()).not.toThrow()
    })
  })

  describe('Shift-End Workflow', () => {
    it('allows shift-end with active shift', () => {
      const store = useWorkflowStore()
      store.activeShift = { id: 1, start_time: new Date().toISOString() }

      const result = store.startWorkflow('shift-end')

      expect(result).toBe(true)
      expect(store.currentWorkflow).toBe('shift-end')
    })

    it('returns shift-end steps', () => {
      const store = useWorkflowStore()
      store.activeShift = { id: 1 }
      store.startWorkflow('shift-end')

      expect(store.workflowSteps.length).toBeGreaterThan(0)
      expect(store.workflowSteps[0].id).toBe('review-completeness')
    })

    it('returns workflow title for shift-end', () => {
      const store = useWorkflowStore()
      store.activeShift = { id: 1 }
      store.startWorkflow('shift-end')

      expect(store.workflowTitle).toBe('End Shift Workflow')
    })
  })

  describe('Current Step Data', () => {
    it('returns current step data', () => {
      const store = useWorkflowStore()
      store.startWorkflow('shift-start')

      const stepData = store.currentStepData

      expect(stepData).toBeDefined()
      expect(stepData.id).toBe('review-previous')
      expect(stepData.title).toBeDefined()
    })

    it('returns null when no workflow', () => {
      const store = useWorkflowStore()

      expect(store.currentStepData).toBeNull()
    })
  })
})
