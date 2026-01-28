/**
 * Workflow Store
 * Manages guided workflow navigation for shift start/end processes
 * Provides step-by-step guidance for manufacturing operators
 */
import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { useAuthStore } from './authStore'
import api from '@/services/api'

const STORAGE_KEY = 'kpi-workflow-progress'

// Workflow step definitions
const SHIFT_START_STEPS = [
  {
    id: 'review-previous',
    title: 'Review Previous Shift',
    description: 'Review key metrics, alerts, and handoff notes from the previous shift',
    icon: 'mdi-clipboard-text-outline',
    required: false,
    component: 'WorkflowStepPreviousShift'
  },
  {
    id: 'confirm-attendance',
    title: 'Confirm Attendance',
    description: 'Verify employee attendance and assign operators to stations',
    icon: 'mdi-account-check',
    required: true,
    component: 'WorkflowStepAttendance'
  },
  {
    id: 'review-targets',
    title: 'Review Production Targets',
    description: 'Review work orders and production targets for the shift',
    icon: 'mdi-target',
    required: true,
    component: 'WorkflowStepTargets'
  },
  {
    id: 'check-equipment',
    title: 'Check Equipment Status',
    description: 'Verify equipment readiness and review any maintenance alerts',
    icon: 'mdi-cog-outline',
    required: false,
    component: 'WorkflowStepEquipment'
  },
  {
    id: 'start-shift',
    title: 'Start Shift',
    description: 'Confirm all preparations and officially start the shift',
    icon: 'mdi-play-circle-outline',
    required: true,
    component: 'WorkflowStepStartShift'
  }
]

const SHIFT_END_STEPS = [
  {
    id: 'review-completeness',
    title: 'Review Data Completeness',
    description: 'Check that all required data entries have been submitted',
    icon: 'mdi-clipboard-check-outline',
    required: true,
    component: 'WorkflowStepCompleteness'
  },
  {
    id: 'complete-production',
    title: 'Complete Production Entries',
    description: 'Submit any pending production entries for the shift',
    icon: 'mdi-factory',
    required: true,
    component: 'WorkflowStepProduction'
  },
  {
    id: 'close-downtime',
    title: 'Close Downtime Records',
    description: 'Ensure all downtime incidents are resolved and documented',
    icon: 'mdi-clock-alert-outline',
    required: true,
    component: 'WorkflowStepDowntime'
  },
  {
    id: 'enter-handoff',
    title: 'Enter Handoff Notes',
    description: 'Document important information for the next shift',
    icon: 'mdi-note-text-outline',
    required: false,
    component: 'WorkflowStepHandoff'
  },
  {
    id: 'generate-summary',
    title: 'Generate Shift Summary',
    description: 'Review the shift summary report before closing',
    icon: 'mdi-file-document-outline',
    required: true,
    component: 'WorkflowStepSummary'
  },
  {
    id: 'end-shift',
    title: 'End Shift',
    description: 'Confirm and officially close the shift',
    icon: 'mdi-stop-circle-outline',
    required: true,
    component: 'WorkflowStepEndShift'
  }
]

export const useWorkflowStore = defineStore('workflow', () => {
  const authStore = useAuthStore()

  // State
  const currentWorkflow = ref(null) // 'shift-start', 'shift-end', null
  const currentStep = ref(0)
  const completedSteps = ref([])
  const skippedSteps = ref([])
  const workflowData = ref({})
  const isLoading = ref(false)
  const error = ref(null)
  const activeShift = ref(null) // Current active shift record

  // Getters
  const workflowSteps = computed(() => {
    if (currentWorkflow.value === 'shift-start') {
      return SHIFT_START_STEPS
    } else if (currentWorkflow.value === 'shift-end') {
      return SHIFT_END_STEPS
    }
    return []
  })

  const totalSteps = computed(() => workflowSteps.value.length)

  const currentStepData = computed(() => {
    if (!workflowSteps.value.length) return null
    return workflowSteps.value[currentStep.value] || null
  })

  const isFirstStep = computed(() => currentStep.value === 0)
  const isLastStep = computed(() => currentStep.value === totalSteps.value - 1)

  const progress = computed(() => {
    if (!totalSteps.value) return 0
    return Math.round(((completedSteps.value.length + skippedSteps.value.length) / totalSteps.value) * 100)
  })

  const canProceed = computed(() => {
    const step = currentStepData.value
    if (!step) return false

    // If step is completed, can proceed
    if (completedSteps.value.includes(step.id)) return true

    // If step is optional and skipped, can proceed
    if (!step.required && skippedSteps.value.includes(step.id)) return true

    // Check if step has validation data
    const stepData = workflowData.value[step.id]
    return stepData?.isValid === true
  })

  const canSkip = computed(() => {
    const step = currentStepData.value
    return step && !step.required
  })

  const hasActiveShift = computed(() => !!activeShift.value)

  const workflowTitle = computed(() => {
    if (currentWorkflow.value === 'shift-start') {
      return 'Start Shift Workflow'
    } else if (currentWorkflow.value === 'shift-end') {
      return 'End Shift Workflow'
    }
    return ''
  })

  // Actions
  const loadFromLocalStorage = () => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored) {
        const data = JSON.parse(stored)
        // Only restore if it's from today and same user
        const today = new Date().toISOString().split('T')[0]
        if (data.date === today && data.userId === authStore.currentUser?.user_id) {
          currentWorkflow.value = data.currentWorkflow
          currentStep.value = data.currentStep
          completedSteps.value = data.completedSteps || []
          skippedSteps.value = data.skippedSteps || []
          workflowData.value = data.workflowData || {}
          activeShift.value = data.activeShift || null
          return true
        }
      }
    } catch (e) {
      console.error('Failed to load workflow progress from localStorage:', e)
    }
    return false
  }

  const saveToLocalStorage = () => {
    try {
      const data = {
        currentWorkflow: currentWorkflow.value,
        currentStep: currentStep.value,
        completedSteps: completedSteps.value,
        skippedSteps: skippedSteps.value,
        workflowData: workflowData.value,
        activeShift: activeShift.value,
        date: new Date().toISOString().split('T')[0],
        userId: authStore.currentUser?.user_id,
        savedAt: new Date().toISOString()
      }
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
    } catch (e) {
      console.error('Failed to save workflow progress to localStorage:', e)
    }
  }

  const startWorkflow = (workflowType) => {
    if (workflowType !== 'shift-start' && workflowType !== 'shift-end') {
      console.error('Invalid workflow type:', workflowType)
      return false
    }

    // Prevent starting shift-end if no active shift
    if (workflowType === 'shift-end' && !hasActiveShift.value) {
      error.value = 'No active shift to end. Please start a shift first.'
      return false
    }

    // Prevent starting shift-start if already have active shift
    if (workflowType === 'shift-start' && hasActiveShift.value) {
      error.value = 'A shift is already active. End the current shift first.'
      return false
    }

    currentWorkflow.value = workflowType
    currentStep.value = 0
    completedSteps.value = []
    skippedSteps.value = []
    workflowData.value = {}
    error.value = null
    saveToLocalStorage()
    return true
  }

  const cancelWorkflow = () => {
    currentWorkflow.value = null
    currentStep.value = 0
    completedSteps.value = []
    skippedSteps.value = []
    workflowData.value = {}
    error.value = null
    saveToLocalStorage()
  }

  const nextStep = () => {
    if (isLastStep.value) return false

    const step = currentStepData.value
    if (step && !completedSteps.value.includes(step.id) && !skippedSteps.value.includes(step.id)) {
      completedSteps.value.push(step.id)
    }

    currentStep.value++
    saveToLocalStorage()
    return true
  }

  const previousStep = () => {
    if (isFirstStep.value) return false
    currentStep.value--
    saveToLocalStorage()
    return true
  }

  const goToStep = (stepIndex) => {
    if (stepIndex < 0 || stepIndex >= totalSteps.value) return false

    // Can only go to completed steps or the current step
    const targetStep = workflowSteps.value[stepIndex]
    if (stepIndex > currentStep.value && !completedSteps.value.includes(targetStep?.id)) {
      return false
    }

    currentStep.value = stepIndex
    saveToLocalStorage()
    return true
  }

  const skipStep = () => {
    if (!canSkip.value) return false

    const step = currentStepData.value
    if (step && !skippedSteps.value.includes(step.id)) {
      skippedSteps.value.push(step.id)
    }

    return nextStep()
  }

  const completeStep = (stepId, data = {}) => {
    const step = workflowSteps.value.find(s => s.id === stepId)
    if (!step) return false

    workflowData.value[stepId] = {
      ...data,
      isValid: true,
      completedAt: new Date().toISOString()
    }

    if (!completedSteps.value.includes(stepId)) {
      completedSteps.value.push(stepId)
    }

    saveToLocalStorage()
    return true
  }

  const updateStepData = (stepId, data) => {
    workflowData.value[stepId] = {
      ...workflowData.value[stepId],
      ...data
    }
    saveToLocalStorage()
  }

  const isStepCompleted = (stepId) => {
    return completedSteps.value.includes(stepId)
  }

  const isStepSkipped = (stepId) => {
    return skippedSteps.value.includes(stepId)
  }

  const getStepStatus = (stepIndex) => {
    const step = workflowSteps.value[stepIndex]
    if (!step) return 'pending'

    if (completedSteps.value.includes(step.id)) return 'completed'
    if (skippedSteps.value.includes(step.id)) return 'skipped'
    if (stepIndex === currentStep.value) return 'current'
    if (stepIndex < currentStep.value) return 'passed'
    return 'pending'
  }

  // API Integration
  const fetchActiveShift = async () => {
    try {
      isLoading.value = true
      const response = await api.get('/shifts/active')
      activeShift.value = response.data
      saveToLocalStorage()
    } catch (e) {
      // No active shift (404) or not authenticated (401/403) are not errors to log
      const status = e.response?.status
      if (status !== 404 && status !== 401 && status !== 403) {
        console.error('Failed to fetch active shift:', e)
      }
      activeShift.value = null
    } finally {
      isLoading.value = false
    }
  }

  const createShift = async (shiftData) => {
    try {
      isLoading.value = true
      error.value = null
      const response = await api.post('/shifts', shiftData)
      activeShift.value = response.data
      saveToLocalStorage()
      return { success: true, data: response.data }
    } catch (e) {
      error.value = e.response?.data?.detail || 'Failed to create shift'
      return { success: false, error: error.value }
    } finally {
      isLoading.value = false
    }
  }

  const endShift = async (shiftId, endData) => {
    try {
      isLoading.value = true
      error.value = null
      const response = await api.patch(`/shifts/${shiftId}/end`, endData)
      activeShift.value = null
      saveToLocalStorage()
      return { success: true, data: response.data }
    } catch (e) {
      error.value = e.response?.data?.detail || 'Failed to end shift'
      return { success: false, error: error.value }
    } finally {
      isLoading.value = false
    }
  }

  const completeWorkflow = async () => {
    if (currentWorkflow.value === 'shift-start') {
      const result = await createShift(workflowData.value)
      if (result.success) {
        cancelWorkflow()
      }
      return result
    } else if (currentWorkflow.value === 'shift-end') {
      if (!activeShift.value?.id) {
        error.value = 'No active shift to end'
        return { success: false, error: error.value }
      }
      const result = await endShift(activeShift.value.id, workflowData.value)
      if (result.success) {
        cancelWorkflow()
      }
      return result
    }
    return { success: false, error: 'No active workflow' }
  }

  // Initialize
  const initialize = async () => {
    loadFromLocalStorage()
    await fetchActiveShift()
  }

  // Watch for auth changes
  watch(() => authStore.currentUser, (newUser) => {
    if (newUser) {
      initialize()
    } else {
      cancelWorkflow()
      activeShift.value = null
    }
  })

  return {
    // State
    currentWorkflow,
    currentStep,
    completedSteps,
    skippedSteps,
    workflowData,
    isLoading,
    error,
    activeShift,

    // Getters
    workflowSteps,
    totalSteps,
    currentStepData,
    isFirstStep,
    isLastStep,
    progress,
    canProceed,
    canSkip,
    hasActiveShift,
    workflowTitle,

    // Actions
    initialize,
    startWorkflow,
    cancelWorkflow,
    nextStep,
    previousStep,
    goToStep,
    skipStep,
    completeStep,
    updateStepData,
    isStepCompleted,
    isStepSkipped,
    getStepStatus,
    completeWorkflow,
    fetchActiveShift,

    // Constants
    SHIFT_START_STEPS,
    SHIFT_END_STEPS
  }
})
