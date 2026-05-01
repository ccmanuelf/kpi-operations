/**
 * Guided shift-start / shift-end workflow store with localStorage
 * persistence and active-shift API sync.
 */
import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { useAuthStore } from './authStore'
import api from '@/services/api'
import i18n from '@/i18n'
import { useNotificationStore } from './notificationStore'

export type WorkflowType = 'shift-start' | 'shift-end' | null
export type StepStatus = 'completed' | 'skipped' | 'current' | 'passed' | 'pending'

export interface WorkflowStep {
  id: string
  title: string
  description: string
  icon: string
  required: boolean
  component: string
}

export interface WorkflowStepData {
  isValid?: boolean
  completedAt?: string
  [key: string]: unknown
}

export interface ActiveShift {
  id?: string | number
  shift_id?: string | number
  [key: string]: unknown
}

export interface ActionResult<T = unknown> {
  success: boolean
  error?: string
  data?: T
}

const t = (key: string): string => i18n.global.t(key)

const STORAGE_KEY = 'kpi-workflow-progress'

const SHIFT_START_STEPS: WorkflowStep[] = [
  {
    id: 'review-previous',
    title: 'Review Previous Shift',
    description: 'Review key metrics, alerts, and handoff notes from the previous shift',
    icon: 'mdi-clipboard-text-outline',
    required: false,
    component: 'WorkflowStepPreviousShift',
  },
  {
    id: 'confirm-attendance',
    title: 'Confirm Attendance',
    description: 'Verify employee attendance and assign operators to stations',
    icon: 'mdi-account-check',
    required: true,
    component: 'WorkflowStepAttendance',
  },
  {
    id: 'review-targets',
    title: 'Review Production Targets',
    description: 'Review work orders and production targets for the shift',
    icon: 'mdi-target',
    required: true,
    component: 'WorkflowStepTargets',
  },
  {
    id: 'check-equipment',
    title: 'Check Equipment Status',
    description: 'Verify equipment readiness and review any maintenance alerts',
    icon: 'mdi-cog-outline',
    required: false,
    component: 'WorkflowStepEquipment',
  },
  {
    id: 'start-shift',
    title: 'Start Shift',
    description: 'Confirm all preparations and officially start the shift',
    icon: 'mdi-play-circle-outline',
    required: true,
    component: 'WorkflowStepStartShift',
  },
]

const SHIFT_END_STEPS: WorkflowStep[] = [
  {
    id: 'review-completeness',
    title: 'Review Data Completeness',
    description: 'Check that all required data entries have been submitted',
    icon: 'mdi-clipboard-check-outline',
    required: true,
    component: 'WorkflowStepCompleteness',
  },
  {
    id: 'complete-production',
    title: 'Complete Production Entries',
    description: 'Submit any pending production entries for the shift',
    icon: 'mdi-factory',
    required: true,
    component: 'WorkflowStepProduction',
  },
  {
    id: 'close-downtime',
    title: 'Close Downtime Records',
    description: 'Ensure all downtime incidents are resolved and documented',
    icon: 'mdi-clock-alert-outline',
    required: true,
    component: 'WorkflowStepDowntime',
  },
  {
    id: 'enter-handoff',
    title: 'Enter Handoff Notes',
    description: 'Document important information for the next shift',
    icon: 'mdi-note-text-outline',
    required: false,
    component: 'WorkflowStepHandoff',
  },
  {
    id: 'generate-summary',
    title: 'Generate Shift Summary',
    description: 'Review the shift summary report before closing',
    icon: 'mdi-file-document-outline',
    required: true,
    component: 'WorkflowStepSummary',
  },
  {
    id: 'end-shift',
    title: 'End Shift',
    description: 'Confirm and officially close the shift',
    icon: 'mdi-stop-circle-outline',
    required: true,
    component: 'WorkflowStepEndShift',
  },
]

const extractDetail = (e: unknown, fallback: string): string => {
  const ax = e as { response?: { data?: { detail?: string } } }
  return ax?.response?.data?.detail || fallback
}

export const useWorkflowStore = defineStore('workflow', () => {
  const authStore = useAuthStore()

  const currentWorkflow = ref<WorkflowType>(null)
  const currentStep = ref(0)
  const completedSteps = ref<string[]>([])
  const skippedSteps = ref<string[]>([])
  const workflowData = ref<Record<string, WorkflowStepData>>({})
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const activeShift = ref<ActiveShift | null>(null)

  const workflowSteps = computed<WorkflowStep[]>(() => {
    if (currentWorkflow.value === 'shift-start') return SHIFT_START_STEPS
    if (currentWorkflow.value === 'shift-end') return SHIFT_END_STEPS
    return []
  })

  const totalSteps = computed(() => workflowSteps.value.length)

  const currentStepData = computed<WorkflowStep | null>(() => {
    if (!workflowSteps.value.length) return null
    return workflowSteps.value[currentStep.value] || null
  })

  const isFirstStep = computed(() => currentStep.value === 0)
  const isLastStep = computed(() => currentStep.value === totalSteps.value - 1)

  const progress = computed(() => {
    if (!totalSteps.value) return 0
    return Math.round(
      ((completedSteps.value.length + skippedSteps.value.length) / totalSteps.value) * 100,
    )
  })

  const canProceed = computed(() => {
    const step = currentStepData.value
    if (!step) return false

    if (completedSteps.value.includes(step.id)) return true
    if (!step.required && skippedSteps.value.includes(step.id)) return true

    const stepData = workflowData.value[step.id]
    return stepData?.isValid === true
  })

  const canSkip = computed(() => {
    const step = currentStepData.value
    return !!step && !step.required
  })

  const hasActiveShift = computed(() => !!activeShift.value)

  const workflowTitle = computed(() => {
    if (currentWorkflow.value === 'shift-start') return 'Start Shift Workflow'
    if (currentWorkflow.value === 'shift-end') return 'End Shift Workflow'
    return ''
  })

  const saveToLocalStorage = (): void => {
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
        savedAt: new Date().toISOString(),
      }
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error('Failed to save workflow progress to localStorage:', e)
    }
  }

  const loadFromLocalStorage = (): boolean => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored) {
        const data = JSON.parse(stored) as {
          date?: string
          userId?: string | number
          currentWorkflow?: WorkflowType
          currentStep?: number
          completedSteps?: string[]
          skippedSteps?: string[]
          workflowData?: Record<string, WorkflowStepData>
          activeShift?: ActiveShift | null
        }
        const today = new Date().toISOString().split('T')[0]
        if (data.date === today && data.userId === authStore.currentUser?.user_id) {
          currentWorkflow.value = data.currentWorkflow ?? null
          currentStep.value = data.currentStep ?? 0
          completedSteps.value = data.completedSteps || []
          skippedSteps.value = data.skippedSteps || []
          workflowData.value = data.workflowData || {}
          activeShift.value = data.activeShift || null
          return true
        }
      }
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error('Failed to load workflow progress from localStorage:', e)
    }
    return false
  }

  const startWorkflow = (workflowType: 'shift-start' | 'shift-end'): boolean => {
    if (workflowType !== 'shift-start' && workflowType !== 'shift-end') {
      // eslint-disable-next-line no-console
      console.error('Invalid workflow type:', workflowType)
      return false
    }

    if (workflowType === 'shift-end' && !hasActiveShift.value) {
      error.value = 'No active shift to end. Please start a shift first.'
      return false
    }

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

  const cancelWorkflow = (): void => {
    currentWorkflow.value = null
    currentStep.value = 0
    completedSteps.value = []
    skippedSteps.value = []
    workflowData.value = {}
    error.value = null
    saveToLocalStorage()
  }

  const nextStep = (): boolean => {
    if (isLastStep.value) return false

    const step = currentStepData.value
    if (
      step &&
      !completedSteps.value.includes(step.id) &&
      !skippedSteps.value.includes(step.id)
    ) {
      completedSteps.value.push(step.id)
    }

    currentStep.value++
    saveToLocalStorage()
    return true
  }

  const previousStep = (): boolean => {
    if (isFirstStep.value) return false
    currentStep.value--
    saveToLocalStorage()
    return true
  }

  const goToStep = (stepIndex: number): boolean => {
    if (stepIndex < 0 || stepIndex >= totalSteps.value) return false

    const targetStep = workflowSteps.value[stepIndex]
    if (
      stepIndex > currentStep.value &&
      !completedSteps.value.includes(targetStep?.id)
    ) {
      return false
    }

    currentStep.value = stepIndex
    saveToLocalStorage()
    return true
  }

  const skipStep = (): boolean => {
    if (!canSkip.value) return false

    const step = currentStepData.value
    if (step && !skippedSteps.value.includes(step.id)) {
      skippedSteps.value.push(step.id)
    }

    return nextStep()
  }

  const completeStep = (stepId: string, data: Record<string, unknown> = {}): boolean => {
    const step = workflowSteps.value.find((s) => s.id === stepId)
    if (!step) return false

    workflowData.value[stepId] = {
      ...data,
      isValid: true,
      completedAt: new Date().toISOString(),
    }

    if (!completedSteps.value.includes(stepId)) {
      completedSteps.value.push(stepId)
    }

    saveToLocalStorage()
    return true
  }

  const updateStepData = (stepId: string, data: Partial<WorkflowStepData>): void => {
    workflowData.value[stepId] = {
      ...workflowData.value[stepId],
      ...data,
    }
    saveToLocalStorage()
  }

  const isStepCompleted = (stepId: string): boolean => completedSteps.value.includes(stepId)
  const isStepSkipped = (stepId: string): boolean => skippedSteps.value.includes(stepId)

  const getStepStatus = (stepIndex: number): StepStatus => {
    const step = workflowSteps.value[stepIndex]
    if (!step) return 'pending'

    if (completedSteps.value.includes(step.id)) return 'completed'
    if (skippedSteps.value.includes(step.id)) return 'skipped'
    if (stepIndex === currentStep.value) return 'current'
    if (stepIndex < currentStep.value) return 'passed'
    return 'pending'
  }

  const fetchActiveShift = async (): Promise<void> => {
    try {
      isLoading.value = true
      const response = await api.get('/shifts/active')
      activeShift.value = response.data
      saveToLocalStorage()
    } catch (e) {
      // No active shift (404) or unauthenticated (401/403) are not errors to log
      const ax = e as { response?: { status?: number } }
      const status = ax?.response?.status
      if (status !== 404 && status !== 401 && status !== 403) {
        // eslint-disable-next-line no-console
        console.error('Failed to fetch active shift:', e)
        useNotificationStore().showError(t('notifications.workflow.activeShiftFetchFailed'))
      }
      activeShift.value = null
    } finally {
      isLoading.value = false
    }
  }

  const createShift = async (
    shiftData: Record<string, unknown>,
  ): Promise<ActionResult<ActiveShift>> => {
    try {
      isLoading.value = true
      error.value = null
      // Trailing slash matches backend `POST /api/shifts/` — without it,
      // FastAPI returns 307 and axios strips Authorization on the redirect.
      const response = await api.post('/shifts/', shiftData)
      activeShift.value = response.data
      saveToLocalStorage()
      return { success: true, data: response.data }
    } catch (e) {
      error.value = extractDetail(e, 'Failed to create shift')
      return { success: false, error: error.value }
    } finally {
      isLoading.value = false
    }
  }

  const endShift = async (
    shiftId: string | number,
    endData: Record<string, unknown>,
  ): Promise<ActionResult> => {
    try {
      isLoading.value = true
      error.value = null
      const response = await api.patch(`/shifts/${shiftId}/end`, endData)
      activeShift.value = null
      saveToLocalStorage()
      return { success: true, data: response.data }
    } catch (e) {
      error.value = extractDetail(e, 'Failed to end shift')
      return { success: false, error: error.value }
    } finally {
      isLoading.value = false
    }
  }

  const completeWorkflow = async (): Promise<ActionResult> => {
    if (currentWorkflow.value === 'shift-start') {
      const result = await createShift(workflowData.value)
      if (result.success) cancelWorkflow()
      return result
    } else if (currentWorkflow.value === 'shift-end') {
      const shiftId = activeShift.value?.id
      if (!shiftId) {
        error.value = 'No active shift to end'
        return { success: false, error: error.value }
      }
      const result = await endShift(shiftId, workflowData.value)
      if (result.success) cancelWorkflow()
      return result
    }
    return { success: false, error: 'No active workflow' }
  }

  const initialize = async (): Promise<void> => {
    loadFromLocalStorage()
    await fetchActiveShift()
  }

  watch(
    () => authStore.currentUser,
    (newUser) => {
      if (newUser) {
        initialize()
      } else {
        cancelWorkflow()
        activeShift.value = null
      }
    },
  )

  return {
    currentWorkflow,
    currentStep,
    completedSteps,
    skippedSteps,
    workflowData,
    isLoading,
    error,
    activeShift,
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
    SHIFT_START_STEPS,
    SHIFT_END_STEPS,
  }
})
