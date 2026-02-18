/**
 * Composable for Workflow Config data fetching, display helpers, and analytics.
 * Handles: clients, templates, config loading, analytics, status/trigger formatting.
 */
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/services/api'
import {
  getWorkflowConfig,
  getWorkflowTemplates,
  getStatusDistribution,
  getClientAverageTimes
} from '@/services/api/workflow'

// All possible workflow statuses
const ALL_STATUSES = [
  'RECEIVED', 'RELEASED', 'DEMOTED', 'ACTIVE', 'IN_PROGRESS',
  'ON_HOLD', 'COMPLETED', 'SHIPPED', 'CLOSED', 'REJECTED', 'CANCELLED'
]

const STATUS_COLORS = {
  RECEIVED: 'blue-grey',
  RELEASED: 'cyan',
  DEMOTED: 'orange',
  ACTIVE: 'info',
  IN_PROGRESS: 'indigo',
  ON_HOLD: 'warning',
  COMPLETED: 'success',
  SHIPPED: 'purple',
  CLOSED: 'grey',
  REJECTED: 'error',
  CANCELLED: 'grey-darken-1'
}

const CLOSURE_TRIGGER_ICONS = {
  at_shipment: 'mdi-truck-delivery',
  at_client_receipt: 'mdi-package-variant-closed-check',
  at_completion: 'mdi-check-circle',
  manual: 'mdi-hand-pointing-right'
}

export default function useWorkflowConfigData() {
  const { t } = useI18n()

  // Loading states
  const loadingClients = ref(false)
  const loadingConfig = ref(false)
  const loadingAnalytics = ref(false)

  // Data
  const clients = ref([])
  const selectedClientId = ref(null)
  const workflowConfig = ref(null)
  const templates = ref([])
  const statusDistribution = ref(null)
  const averageTimes = ref(null)

  // Constants
  const allStatuses = ALL_STATUSES

  // Computed
  const selectedClientName = computed(() => {
    const client = clients.value.find(c => c.client_id === selectedClientId.value)
    return client?.client_name || selectedClientId.value
  })

  // Formatting helpers
  const getStatusColor = (status) => STATUS_COLORS[status] || 'grey'

  const formatStatus = (status) => {
    const labels = {
      RECEIVED: t('workflow.status.received'),
      RELEASED: t('workflow.status.released'),
      DEMOTED: t('workflow.status.demoted'),
      ACTIVE: t('workflow.status.active'),
      IN_PROGRESS: t('workflow.status.in_wip'),
      ON_HOLD: t('workflow.status.on_hold'),
      COMPLETED: t('workflow.status.completed'),
      SHIPPED: t('workflow.status.shipped'),
      CLOSED: t('workflow.status.closed'),
      REJECTED: t('workflow.status.rejected'),
      CANCELLED: t('workflow.status.cancelled')
    }
    return labels[status] || status
  }

  const formatClosureTrigger = (trigger) => {
    const labels = {
      at_shipment: t('admin.workflowConfig.closureTriggers.atShipment'),
      at_client_receipt: t('admin.workflowConfig.closureTriggers.atClientReceipt'),
      at_completion: t('admin.workflowConfig.closureTriggers.atCompletion'),
      manual: t('admin.workflowConfig.closureTriggers.manual')
    }
    return labels[trigger] || trigger
  }

  const getClosureTriggerIcon = (trigger) => CLOSURE_TRIGGER_ICONS[trigger] || 'mdi-help-circle'

  const getClosureTriggerHint = (trigger) => {
    const hints = {
      at_shipment: t('admin.workflowConfig.closureHints.atShipment'),
      at_client_receipt: t('admin.workflowConfig.closureHints.atClientReceipt'),
      at_completion: t('admin.workflowConfig.closureHints.atCompletion'),
      manual: t('admin.workflowConfig.closureHints.manual')
    }
    return hints[trigger] || ''
  }

  const closureTriggerOptions = [
    { title: t('admin.workflowConfig.closureTriggers.atShipment'), value: 'at_shipment' },
    { title: t('admin.workflowConfig.closureTriggers.atClientReceipt'), value: 'at_client_receipt' },
    { title: t('admin.workflowConfig.closureTriggers.atCompletion'), value: 'at_completion' },
    { title: t('admin.workflowConfig.closureTriggers.manual'), value: 'manual' }
  ]

  // Data loading
  const loadClients = async () => {
    loadingClients.value = true
    try {
      const response = await api.get('/clients')
      clients.value = response.data
    } catch (error) {
      console.error('Failed to load clients:', error)
      throw error
    } finally {
      loadingClients.value = false
    }
  }

  const loadTemplates = async () => {
    try {
      const response = await getWorkflowTemplates()
      templates.value = response.data.templates || []
    } catch (error) {
      console.error('Failed to load templates:', error)
    }
  }

  const loadAnalytics = async () => {
    if (!selectedClientId.value) return

    loadingAnalytics.value = true
    try {
      const [distResponse, timesResponse] = await Promise.all([
        getStatusDistribution(selectedClientId.value),
        getClientAverageTimes(selectedClientId.value)
      ])
      statusDistribution.value = distResponse.data
      averageTimes.value = timesResponse.data
    } catch (error) {
      console.error('Failed to load analytics:', error)
      statusDistribution.value = null
      averageTimes.value = null
    } finally {
      loadingAnalytics.value = false
    }
  }

  const loadClientConfig = async () => {
    if (!selectedClientId.value) {
      workflowConfig.value = null
      statusDistribution.value = null
      averageTimes.value = null
      return
    }

    loadingConfig.value = true
    try {
      const response = await getWorkflowConfig(selectedClientId.value)
      workflowConfig.value = response.data
      await loadAnalytics()
    } catch (error) {
      console.error('Failed to load workflow config:', error)
      throw error
    } finally {
      loadingConfig.value = false
    }
  }

  return {
    // State
    loadingClients,
    loadingConfig,
    loadingAnalytics,
    clients,
    selectedClientId,
    workflowConfig,
    templates,
    statusDistribution,
    averageTimes,

    // Constants
    allStatuses,
    closureTriggerOptions,

    // Computed
    selectedClientName,

    // Formatting
    getStatusColor,
    formatStatus,
    formatClosureTrigger,
    getClosureTriggerIcon,
    getClosureTriggerHint,

    // Data loading
    loadClients,
    loadTemplates,
    loadAnalytics,
    loadClientConfig
  }
}
