/**
 * Composable for Part Opportunities data fetching, filtering, and
 * display helpers (avg/min/max stats, color tokens, table headers).
 */
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/services/api'

export interface ClientOption {
  client_id: string | number | null
  client_name: string
  [key: string]: unknown
}

export interface PartOpportunity {
  part_number?: string
  part_description?: string
  opportunities_per_unit?: number
  complexity?: string
  is_active?: boolean
  [key: string]: unknown
}

export type ComplexityLevel = 'Simple' | 'Standard' | 'Complex' | 'Very Complex' | string
export type SnackbarColor = 'success' | 'error' | 'warning' | 'info'
export type StatusColor = 'success' | 'info' | 'warning' | 'error' | 'grey'

export interface SnackbarState {
  show: boolean
  message: string
  color: SnackbarColor
}

export interface TableHeader {
  title: string
  key: string
  sortable: boolean
  align?: 'start' | 'center' | 'end'
}

export function usePartOpportunitiesData() {
  const { t } = useI18n()

  const loading = ref(false)

  const clients = ref<ClientOption[]>([])
  const selectedClient = ref<string | number | null>(null)
  const partOpportunities = ref<PartOpportunity[]>([])
  const search = ref('')

  const snackbar = ref<SnackbarState>({
    show: false,
    message: '',
    color: 'success',
  })

  const showSnackbar = (message: string, color: SnackbarColor = 'success'): void => {
    snackbar.value = { show: true, message, color }
  }

  const clientOptions = computed<ClientOption[]>(() => [
    { client_id: null, client_name: t('common.all') },
    ...clients.value,
  ])

  const averageOpportunities = computed<number>(() => {
    if (partOpportunities.value.length === 0) return 0
    const sum = partOpportunities.value.reduce(
      (acc, p) => acc + (p.opportunities_per_unit || 0),
      0,
    )
    return Math.round(sum / partOpportunities.value.length)
  })

  const minOpportunities = computed<number>(() => {
    if (partOpportunities.value.length === 0) return 0
    return Math.min(...partOpportunities.value.map((p) => p.opportunities_per_unit || 0))
  })

  const maxOpportunities = computed<number>(() => {
    if (partOpportunities.value.length === 0) return 0
    return Math.max(...partOpportunities.value.map((p) => p.opportunities_per_unit || 0))
  })

  const headers = computed<TableHeader[]>(() => [
    { title: t('jobs.partNumber'), key: 'part_number', sortable: true },
    { title: t('admin.partDescription'), key: 'part_description', sortable: true },
    { title: t('admin.opportunitiesPerUnit'), key: 'opportunities_per_unit', sortable: true },
    { title: t('admin.complexity'), key: 'complexity', sortable: true },
    { title: t('common.active'), key: 'is_active', sortable: true },
    { title: t('common.actions'), key: 'actions', sortable: false, align: 'end' },
  ])

  const getOpportunityColor = (count: number): StatusColor => {
    if (count <= 5) return 'success'
    if (count <= 15) return 'info'
    if (count <= 30) return 'warning'
    return 'error'
  }

  const getComplexityColor = (complexity: ComplexityLevel): StatusColor => {
    switch (complexity) {
      case 'Simple':
        return 'success'
      case 'Standard':
        return 'info'
      case 'Complex':
        return 'warning'
      case 'Very Complex':
        return 'error'
      default:
        return 'grey'
    }
  }

  const loadClients = async (): Promise<void> => {
    try {
      const res = await api.getClients()
      clients.value = res.data || []
    } catch {
      showSnackbar(t('errors.general'), 'error')
    }
  }

  const loadPartOpportunities = async (): Promise<void> => {
    loading.value = true
    try {
      const params: Record<string, unknown> = {}
      if (selectedClient.value) {
        params.client_id = selectedClient.value
      }
      const res = await api.get('/part-opportunities', { params })
      partOpportunities.value = res.data || []
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to load part opportunities:', error)
      partOpportunities.value = []
    } finally {
      loading.value = false
    }
  }

  return {
    loading,
    clients,
    selectedClient,
    partOpportunities,
    search,
    snackbar,
    clientOptions,
    averageOpportunities,
    minOpportunities,
    maxOpportunities,
    headers,
    showSnackbar,
    getOpportunityColor,
    getComplexityColor,
    loadClients,
    loadPartOpportunities,
  }
}
