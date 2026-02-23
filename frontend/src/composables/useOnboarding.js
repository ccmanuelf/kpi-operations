/**
 * Composable for on-demand onboarding checklist state.
 *
 * Manages dialog visibility, step completion status, and API calls
 * for the Getting Started checklist feature.
 */
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { getOnboardingStatus } from '@/services/api/onboarding'

/**
 * Onboarding step definitions with route links and icon mappings.
 * Order matches the operational workflow.
 */
const STEP_DEFINITIONS = [
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
  const status = ref(null)
  const loading = ref(false)
  const error = ref(null)

  /** Enriched step list combining definitions with live completion status. */
  const steps = computed(() => {
    return STEP_DEFINITIONS.map((def) => ({
      ...def,
      title: t(`${def.i18nKey}.title`),
      description: t(`${def.i18nKey}.description`),
      completed: status.value?.steps?.[def.key] ?? false,
    }))
  })

  /** Number of completed steps. */
  const completedCount = computed(() => status.value?.completed_count ?? 0)

  /** Total number of steps. */
  const totalSteps = computed(() => status.value?.total_steps ?? STEP_DEFINITIONS.length)

  /** Whether all steps are complete. */
  const allComplete = computed(() => status.value?.all_complete ?? false)

  /** Progress percentage (0-100). */
  const progressPercent = computed(() => {
    if (totalSteps.value === 0) return 0
    return Math.round((completedCount.value / totalSteps.value) * 100)
  })

  /**
   * Fetch the current onboarding status from the backend.
   * @param {string} [clientId] - Optional client_id override
   */
  async function checkStatus(clientId) {
    loading.value = true
    error.value = null
    try {
      const params = {}
      if (clientId) {
        params.client_id = clientId
      }
      const response = await getOnboardingStatus(params)
      status.value = response.data
    } catch (err) {
      error.value = err.response?.data?.detail || t('common.error')
      console.error('Failed to fetch onboarding status:', err)
    } finally {
      loading.value = false
    }
  }

  /**
   * Open the onboarding dialog and refresh status.
   * @param {string} [clientId] - Optional client_id override
   */
  function openOnboarding(clientId) {
    showOnboarding.value = true
    checkStatus(clientId)
  }

  /** Close the onboarding dialog. */
  function dismissOnboarding() {
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
