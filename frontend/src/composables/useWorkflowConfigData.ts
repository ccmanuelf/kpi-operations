/**
 * Composable for Workflow Config data fetching, display helpers,
 * and analytics. Clients, templates, config loading, status/
 * trigger formatting, distribution and average-times analytics.
 */
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/services/api'
import {
  getWorkflowConfig,
  getWorkflowTemplates,
  getStatusDistribution,
  getClientAverageTimes,
} from '@/services/api/workflow'

export type WorkflowStatus =
  | 'RECEIVED'
  | 'RELEASED'
  | 'DEMOTED'
  | 'ACTIVE'
  | 'IN_PROGRESS'
  | 'ON_HOLD'
  | 'COMPLETED'
  | 'SHIPPED'
  | 'CLOSED'
  | 'REJECTED'
  | 'CANCELLED'

export type ClosureTrigger =
  | 'at_shipment'
  | 'at_client_receipt'
  | 'at_completion'
  | 'manual'

export interface ClientRow {
  client_id: string | number
  client_name?: string
  [key: string]: unknown
}

export interface TriggerOption {
  title: string
  value: ClosureTrigger
}

const ALL_STATUSES: WorkflowStatus[] = [
  'RECEIVED',
  'RELEASED',
  'DEMOTED',
  'ACTIVE',
  'IN_PROGRESS',
  'ON_HOLD',
  'COMPLETED',
  'SHIPPED',
  'CLOSED',
  'REJECTED',
  'CANCELLED',
]

const STATUS_COLORS: Record<WorkflowStatus, string> = {
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
  CANCELLED: 'grey-darken-1',
}

const CLOSURE_TRIGGER_ICONS: Record<ClosureTrigger, string> = {
  at_shipment: 'mdi-truck-delivery',
  at_client_receipt: 'mdi-package-variant-closed-check',
  at_completion: 'mdi-check-circle',
  manual: 'mdi-hand-pointing-right',
}

export default function useWorkflowConfigData() {
  const { t } = useI18n()

  const loadingClients = ref(false)
  const loadingConfig = ref(false)
  const loadingAnalytics = ref(false)

  const clients = ref<ClientRow[]>([])
  const selectedClientId = ref<string | number | null>(null)
  const workflowConfig = ref<unknown | null>(null)
  const templates = ref<unknown[]>([])
  const statusDistribution = ref<unknown | null>(null)
  const averageTimes = ref<unknown | null>(null)

  const allStatuses = ALL_STATUSES

  const selectedClientName = computed<string | number | null>(() => {
    const client = clients.value.find((c) => c.client_id === selectedClientId.value)
    return client?.client_name || selectedClientId.value
  })

  const getStatusColor = (status: WorkflowStatus | string): string =>
    STATUS_COLORS[status as WorkflowStatus] || 'grey'

  const formatStatus = (status: WorkflowStatus | string): string => {
    const labels: Record<WorkflowStatus, string> = {
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
      CANCELLED: t('workflow.status.cancelled'),
    }
    return labels[status as WorkflowStatus] || status
  }

  const formatClosureTrigger = (trigger: ClosureTrigger | string): string => {
    const labels: Record<ClosureTrigger, string> = {
      at_shipment: t('admin.workflowConfig.closureTriggers.atShipment'),
      at_client_receipt: t('admin.workflowConfig.closureTriggers.atClientReceipt'),
      at_completion: t('admin.workflowConfig.closureTriggers.atCompletion'),
      manual: t('admin.workflowConfig.closureTriggers.manual'),
    }
    return labels[trigger as ClosureTrigger] || trigger
  }

  const getClosureTriggerIcon = (trigger: ClosureTrigger | string): string =>
    CLOSURE_TRIGGER_ICONS[trigger as ClosureTrigger] || 'mdi-help-circle'

  const getClosureTriggerHint = (trigger: ClosureTrigger | string): string => {
    const hints: Record<ClosureTrigger, string> = {
      at_shipment: t('admin.workflowConfig.closureHints.atShipment'),
      at_client_receipt: t('admin.workflowConfig.closureHints.atClientReceipt'),
      at_completion: t('admin.workflowConfig.closureHints.atCompletion'),
      manual: t('admin.workflowConfig.closureHints.manual'),
    }
    return hints[trigger as ClosureTrigger] || ''
  }

  const closureTriggerOptions: TriggerOption[] = [
    { title: t('admin.workflowConfig.closureTriggers.atShipment'), value: 'at_shipment' },
    {
      title: t('admin.workflowConfig.closureTriggers.atClientReceipt'),
      value: 'at_client_receipt',
    },
    { title: t('admin.workflowConfig.closureTriggers.atCompletion'), value: 'at_completion' },
    { title: t('admin.workflowConfig.closureTriggers.manual'), value: 'manual' },
  ]

  const loadClients = async (): Promise<void> => {
    loadingClients.value = true
    try {
      const response = await api.get('/clients')
      clients.value = response.data
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to load clients:', error)
      throw error
    } finally {
      loadingClients.value = false
    }
  }

  const loadTemplates = async (): Promise<void> => {
    try {
      const response = await getWorkflowTemplates()
      templates.value = (response.data as { templates?: unknown[] }).templates || []
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to load templates:', error)
    }
  }

  const loadAnalytics = async (): Promise<void> => {
    if (!selectedClientId.value) return

    loadingAnalytics.value = true
    try {
      const [distResponse, timesResponse] = await Promise.all([
        getStatusDistribution(selectedClientId.value),
        getClientAverageTimes(selectedClientId.value),
      ])
      statusDistribution.value = distResponse.data
      averageTimes.value = timesResponse.data
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to load analytics:', error)
      statusDistribution.value = null
      averageTimes.value = null
    } finally {
      loadingAnalytics.value = false
    }
  }

  const loadClientConfig = async (): Promise<void> => {
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
      // eslint-disable-next-line no-console
      console.error('Failed to load workflow config:', error)
      throw error
    } finally {
      loadingConfig.value = false
    }
  }

  return {
    loadingClients,
    loadingConfig,
    loadingAnalytics,
    clients,
    selectedClientId,
    workflowConfig,
    templates,
    statusDistribution,
    averageTimes,
    allStatuses,
    closureTriggerOptions,
    selectedClientName,
    getStatusColor,
    formatStatus,
    formatClosureTrigger,
    getClosureTriggerIcon,
    getClosureTriggerHint,
    loadClients,
    loadTemplates,
    loadAnalytics,
    loadClientConfig,
  }
}
