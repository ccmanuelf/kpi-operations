/**
 * Composable for Defect Types data fetching, filtering, and display helpers.
 * Handles: clients, defect types list, loading, table headers, constants, formatting.
 */
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/services/api'

const GLOBAL_CLIENT_ID = 'GLOBAL'

const SEVERITIES = ['CRITICAL', 'MAJOR', 'MINOR']

const CATEGORIES = [
  'Assembly', 'Material', 'Process', 'Electrical', 'Finish',
  'Measurement', 'Sewing', 'Packaging', 'Labeling', 'Cleanliness',
  'Testing', 'Documentation', 'Handling', 'Environment', 'General'
]

const VALIDATION_RULES = {
  required: v => !!v || 'Required',
  maxLength20: v => !v || v.length <= 20 || 'Max 20 characters',
  maxLength100: v => !v || v.length <= 100 || 'Max 100 characters'
}

export default function useDefectTypesData() {
  const { t } = useI18n()

  // Loading state
  const loading = ref(false)

  // Data
  const clients = ref([])
  const selectedClient = ref(null)
  const defectTypes = ref([])
  const search = ref('')

  // Constants
  const severities = SEVERITIES
  const categories = CATEGORIES
  const rules = VALIDATION_RULES

  // Table headers
  const headers = [
    { title: 'Code', key: 'defect_code', sortable: true },
    { title: 'Name', key: 'defect_name', sortable: true },
    { title: 'Category', key: 'category', sortable: true },
    { title: 'Severity', key: 'severity_default', sortable: true },
    { title: 'Standard', key: 'industry_standard_code', sortable: true },
    { title: 'Order', key: 'sort_order', sortable: true },
    { title: 'Active', key: 'is_active', sortable: true },
    { title: 'Actions', key: 'actions', sortable: false, align: 'end' }
  ]

  // Computed
  const clientOptions = computed(() => {
    const globalOption = {
      client_id: GLOBAL_CLIENT_ID,
      client_name: t('admin.defectTypes.globalAllClients')
    }
    return [globalOption, ...clients.value]
  })

  const isGlobalSelected = computed(() => selectedClient.value === GLOBAL_CLIENT_ID)

  const selectedClientInfo = computed(() => {
    if (isGlobalSelected.value) {
      return { client_id: GLOBAL_CLIENT_ID, client_name: t('admin.defectTypes.globalAllClients') }
    }
    return clients.value.find(c => c.client_id === selectedClient.value)
  })

  // Formatting
  const getSeverityColor = (severity) => {
    switch (severity) {
      case 'CRITICAL': return 'error'
      case 'MAJOR': return 'warning'
      case 'MINOR': return 'info'
      default: return 'grey'
    }
  }

  // Data loading
  const loadClients = async () => {
    try {
      const res = await api.getClients()
      clients.value = res.data || []
    } catch (error) {
      console.error('Failed to load clients:', error)
      throw error
    }
  }

  const loadDefectTypes = async () => {
    if (!selectedClient.value) {
      defectTypes.value = []
      return
    }

    loading.value = true
    try {
      const includeGlobal = false
      const res = await api.getDefectTypesByClient(selectedClient.value, false, includeGlobal)
      defectTypes.value = res.data || []
    } catch (error) {
      console.error('Failed to load defect types:', error)
      defectTypes.value = []
      throw error
    } finally {
      loading.value = false
    }
  }

  return {
    // Constants
    GLOBAL_CLIENT_ID,
    severities,
    categories,
    rules,
    headers,

    // State
    loading,
    clients,
    selectedClient,
    defectTypes,
    search,

    // Computed
    clientOptions,
    isGlobalSelected,
    selectedClientInfo,

    // Formatting
    getSeverityColor,

    // Data loading
    loadClients,
    loadDefectTypes
  }
}
