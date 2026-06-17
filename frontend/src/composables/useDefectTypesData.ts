/**
 * Composable for Defect Types data fetching, filtering, and
 * display helpers.
 */
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/services/api'

export type Severity = 'CRITICAL' | 'MAJOR' | 'MINOR'
export type StatusColor = 'error' | 'warning' | 'info' | 'grey'

export interface ClientOption {
  client_id: string | number
  client_name: string
  [key: string]: unknown
}

export interface DefectType {
  defect_code?: string
  defect_name?: string
  category?: string
  severity_default?: Severity
  industry_standard_code?: string
  sort_order?: number
  is_active?: boolean
  [key: string]: unknown
}

export interface TableHeader {
  title: string
  key: string
  sortable: boolean
  align?: 'start' | 'center' | 'end'
}

export type ValidationRule = (_v: string | null | undefined) => true | string

export interface ValidationRules {
  required: ValidationRule
  maxLength20: ValidationRule
  maxLength100: ValidationRule
}

const GLOBAL_CLIENT_ID = 'GLOBAL'

const SEVERITIES: Severity[] = ['CRITICAL', 'MAJOR', 'MINOR']

const CATEGORIES: string[] = [
  'Assembly',
  'Material',
  'Process',
  'Electrical',
  'Finish',
  'Measurement',
  'Sewing',
  'Packaging',
  'Labeling',
  'Cleanliness',
  'Testing',
  'Documentation',
  'Handling',
  'Environment',
  'General',
]

export default function useDefectTypesData() {
  const { t } = useI18n()

  const VALIDATION_RULES: ValidationRules = {
    required: (v) => !!v || t('validation.requiredShort'),
    maxLength20: (v) => !v || v.length <= 20 || t('validation.maxChars', { n: 20 }),
    maxLength100: (v) => !v || v.length <= 100 || t('validation.maxChars', { n: 100 }),
  }

  const loading = ref(false)

  const clients = ref<ClientOption[]>([])
  const selectedClient = ref<string | number | null>(null)
  const defectTypes = ref<DefectType[]>([])
  const search = ref('')

  const severities = SEVERITIES
  const categories = CATEGORIES
  const rules = VALIDATION_RULES

  const headers = computed<TableHeader[]>(() => [
    { title: t('admin.defectTypes.tableHeaders.code'), key: 'defect_code', sortable: true },
    { title: t('admin.defectTypes.tableHeaders.name'), key: 'defect_name', sortable: true },
    { title: t('admin.defectTypes.tableHeaders.category'), key: 'category', sortable: true },
    { title: t('admin.defectTypes.tableHeaders.severity'), key: 'severity_default', sortable: true },
    { title: t('admin.defectTypes.tableHeaders.standard'), key: 'industry_standard_code', sortable: true },
    { title: t('admin.defectTypes.tableHeaders.order'), key: 'sort_order', sortable: true },
    { title: t('admin.defectTypes.tableHeaders.active'), key: 'is_active', sortable: true },
    { title: t('admin.defectTypes.tableHeaders.actions'), key: 'actions', sortable: false, align: 'end' },
  ])

  const clientOptions = computed<ClientOption[]>(() => {
    const globalOption: ClientOption = {
      client_id: GLOBAL_CLIENT_ID,
      client_name: t('admin.defectTypes.globalAllClients'),
    }
    return [globalOption, ...clients.value]
  })

  const isGlobalSelected = computed<boolean>(
    () => selectedClient.value === GLOBAL_CLIENT_ID,
  )

  const selectedClientInfo = computed<ClientOption | undefined>(() => {
    if (isGlobalSelected.value) {
      return {
        client_id: GLOBAL_CLIENT_ID,
        client_name: t('admin.defectTypes.globalAllClients'),
      }
    }
    return clients.value.find((c) => c.client_id === selectedClient.value)
  })

  const getSeverityColor = (severity: Severity | string | undefined): StatusColor => {
    switch (severity) {
      case 'CRITICAL':
        return 'error'
      case 'MAJOR':
        return 'warning'
      case 'MINOR':
        return 'info'
      default:
        return 'grey'
    }
  }

  const loadClients = async (): Promise<void> => {
    try {
      const res = await api.getClients()
      clients.value = res.data || []
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to load clients:', error)
      throw error
    }
  }

  const loadDefectTypes = async (): Promise<void> => {
    if (!selectedClient.value) {
      defectTypes.value = []
      return
    }

    loading.value = true
    try {
      const includeGlobal = false
      const res = await api.getDefectTypesByClient(
        selectedClient.value,
        false,
        includeGlobal,
      )
      defectTypes.value = res.data || []
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to load defect types:', error)
      defectTypes.value = []
      throw error
    } finally {
      loading.value = false
    }
  }

  return {
    GLOBAL_CLIENT_ID,
    severities,
    categories,
    rules,
    headers,
    loading,
    clients,
    selectedClient,
    defectTypes,
    search,
    clientOptions,
    isGlobalSelected,
    selectedClientInfo,
    getSeverityColor,
    loadClients,
    loadDefectTypes,
  }
}
