/**
 * Composable for the on-demand onboarding checklist. Manages the
 * dialog visibility, step completion status, and the API call
 * that pulls live status from the backend.
 */
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { getOnboardingStatus } from '@/services/api/onboarding'

export interface OnboardingStepDefinition {
  key: string
  i18nKey: string
  icon: string
  route: string
  color: string
}

export interface OnboardingStep extends OnboardingStepDefinition {
  title: string
  description: string
  completed: boolean
}

export interface OnboardingStatus {
  steps?: Record<string, boolean>
  completed_count?: number
  total_steps?: number
  all_complete?: boolean
  [key: string]: unknown
}

const STEP_DEFINITIONS: OnboardingStepDefinition[] = [
  {
    key: 'shifts_configured',
    i18nKey: 'onboarding.steps.shifts',
    icon: 'mdi-clock-outline',
    route: '/admin/settings',
    color: 'blue',
  },
  {
    key: 'products_added',
    i18nKey: 'onboarding.steps.products',
    icon: 'mdi-package-variant-closed',
    route: '/admin/settings',
    color: 'green',
  },
  {
    key: 'work_orders_created',
    i18nKey: 'onboarding.steps.workOrders',
    icon: 'mdi-clipboard-list-outline',
    route: '/work-orders',
    color: 'orange',
  },
  {
    key: 'production_data_entered',
    i18nKey: 'onboarding.steps.production',
    icon: 'mdi-factory',
    route: '/production-entry',
    color: 'purple',
  },
  {
    key: 'capacity_plan_created',
    i18nKey: 'onboarding.steps.kpi',
    icon: 'mdi-chart-line',
    route: '/kpi-dashboard',
    color: 'red',
  },
]

export function useOnboarding() {
  const { t } = useI18n()

  const showOnboarding = ref(false)
  const status = ref<OnboardingStatus | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const steps = computed<OnboardingStep[]>(() =>
    STEP_DEFINITIONS.map((def) => ({
      ...def,
      title: t(`${def.i18nKey}.title`),
      description: t(`${def.i18nKey}.description`),
      completed: status.value?.steps?.[def.key] ?? false,
    })),
  )

  const completedCount = computed<number>(() => status.value?.completed_count ?? 0)
  const totalSteps = computed<number>(
    () => status.value?.total_steps ?? STEP_DEFINITIONS.length,
  )
  const allComplete = computed<boolean>(() => status.value?.all_complete ?? false)

  const progressPercent = computed<number>(() => {
    if (totalSteps.value === 0) return 0
    return Math.round((completedCount.value / totalSteps.value) * 100)
  })

  async function checkStatus(clientId?: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const params: { client_id?: string } = {}
      if (clientId) {
        params.client_id = clientId
      }
      const response = await getOnboardingStatus(params)
      status.value = response.data as OnboardingStatus
    } catch (err) {
      const ax = err as { response?: { data?: { detail?: string } } }
      error.value = ax?.response?.data?.detail || t('common.error')
      // eslint-disable-next-line no-console
      console.error('Failed to fetch onboarding status:', err)
    } finally {
      loading.value = false
    }
  }

  function openOnboarding(clientId?: string): void {
    showOnboarding.value = true
    checkStatus(clientId)
  }

  function dismissOnboarding(): void {
    showOnboarding.value = false
  }

  return {
    showOnboarding,
    status,
    loading,
    error,
    steps,
    completedCount,
    totalSteps,
    allComplete,
    progressPercent,
    checkStatus,
    openOnboarding,
    dismissOnboarding,
  }
}
