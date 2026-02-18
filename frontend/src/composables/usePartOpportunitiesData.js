/**
 * Composable for Part Opportunities data fetching, filtering, and display helpers.
 * Handles: loading state, part opportunities list, client list, search,
 *          summary stats (avg/min/max), table headers, color helpers, snackbar.
 */
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/services/api'

export function usePartOpportunitiesData() {
  const { t } = useI18n()

  // Loading state
  const loading = ref(false)

  // Data
  const clients = ref([])
  const selectedClient = ref(null)
  const partOpportunities = ref([])
  const search = ref('')

  // Snackbar
  const snackbar = ref({
    show: false,
    message: '',
    color: 'success'
  })

  const showSnackbar = (message, color = 'success') => {
    snackbar.value = { show: true, message, color }
  }

  // Computed
  const clientOptions = computed(() => {
    return [{ client_id: null, client_name: t('common.all') }, ...clients.value]
  })

  const averageOpportunities = computed(() => {
    if (partOpportunities.value.length === 0) return 0
    const sum = partOpportunities.value.reduce((acc, p) => acc + (p.opportunities_per_unit || 0), 0)
    return Math.round(sum / partOpportunities.value.length)
  })

  const minOpportunities = computed(() => {
    if (partOpportunities.value.length === 0) return 0
    return Math.min(...partOpportunities.value.map(p => p.opportunities_per_unit || 0))
  })

  const maxOpportunities = computed(() => {
    if (partOpportunities.value.length === 0) return 0
    return Math.max(...partOpportunities.value.map(p => p.opportunities_per_unit || 0))
  })

  const headers = computed(() => [
    { title: t('jobs.partNumber'), key: 'part_number', sortable: true },
    { title: t('admin.partDescription'), key: 'part_description', sortable: true },
    { title: t('admin.opportunitiesPerUnit'), key: 'opportunities_per_unit', sortable: true },
    { title: t('admin.complexity'), key: 'complexity', sortable: true },
    { title: t('common.active'), key: 'is_active', sortable: true },
    { title: t('common.actions'), key: 'actions', sortable: false, align: 'end' }
  ])

  // Display helpers
  const getOpportunityColor = (count) => {
    if (count <= 5) return 'success'
    if (count <= 15) return 'info'
    if (count <= 30) return 'warning'
    return 'error'
  }

  const getComplexityColor = (complexity) => {
    switch (complexity) {
      case 'Simple': return 'success'
      case 'Standard': return 'info'
      case 'Complex': return 'warning'
      case 'Very Complex': return 'error'
      default: return 'grey'
    }
  }

  // Data fetching
  const loadClients = async () => {
    try {
      const res = await api.getClients()
      clients.value = res.data || []
    } catch (error) {
      showSnackbar(t('errors.general'), 'error')
    }
  }

  const loadPartOpportunities = async () => {
    loading.value = true
    try {
      const params = {}
      if (selectedClient.value) {
        params.client_id = selectedClient.value
      }
      const res = await api.get('/part-opportunities', { params })
      partOpportunities.value = res.data || []
    } catch (error) {
      console.error('Failed to load part opportunities:', error)
      partOpportunities.value = []
    } finally {
      loading.value = false
    }
  }

  return {
    // State
    loading,
    clients,
    selectedClient,
    partOpportunities,
    search,
    snackbar,

    // Computed
    clientOptions,
    averageOpportunities,
    minOpportunities,
    maxOpportunities,
    headers,

    // Methods
    showSnackbar,
    getOpportunityColor,
    getComplexityColor,
    loadClients,
    loadPartOpportunities
  }
}
