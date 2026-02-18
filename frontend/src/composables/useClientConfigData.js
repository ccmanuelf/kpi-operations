/**
 * Composable for Client Config data fetching and display logic.
 * Handles: clients list, global defaults, client config loading, formatting.
 */
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/services/api'

export function useClientConfigData() {
  const { t } = useI18n()

  // Loading states
  const loadingClients = ref(false)
  const loadingConfig = ref(false)

  // Data state
  const clients = ref([])
  const selectedClientId = ref(null)
  const clientConfig = ref(null)
  const globalDefaults = ref(null)

  // Snackbar
  const snackbar = ref({ show: false, text: '', color: 'success' })

  // Computed
  const selectedClientName = computed(() => {
    const client = clients.value.find(c => c.client_id === selectedClientId.value)
    return client?.client_name || selectedClientId.value
  })

  // Formatting helpers
  const formatLabel = (key) => {
    return key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
  }

  const formatValue = (key, value) => {
    if (value === null || value === undefined) return '-'
    if (key.includes('percent')) return `${value}%`
    if (key.includes('hours')) return `${value} hrs`
    if (key.includes('days')) return `${value} days`
    if (key.includes('ppm')) return `${value.toLocaleString()} PPM`
    return value
  }

  const showSnackbar = (text, color) => {
    snackbar.value = { show: true, text, color }
  }

  // Data fetching
  const loadClients = async () => {
    loadingClients.value = true
    try {
      const response = await api.get('/clients')
      clients.value = response.data
    } catch (error) {
      console.error('Failed to load clients:', error)
      showSnackbar(t('admin.clientConfig.errors.loadClients'), 'error')
    } finally {
      loadingClients.value = false
    }
  }

  const loadGlobalDefaults = async () => {
    try {
      const response = await api.get('/client-config/defaults')
      globalDefaults.value = response.data
    } catch (error) {
      console.error('Failed to load global defaults:', error)
    }
  }

  const loadClientConfig = async () => {
    if (!selectedClientId.value) {
      clientConfig.value = null
      return
    }

    loadingConfig.value = true
    try {
      const response = await api.get(`/client-config/${selectedClientId.value}`)
      clientConfig.value = response.data
    } catch (error) {
      if (error.response?.status === 404) {
        // No config exists - show defaults indicator
        clientConfig.value = {
          is_default: true,
          config: { ...globalDefaults.value }
        }
      } else {
        console.error('Failed to load client config:', error)
        showSnackbar(t('admin.clientConfig.errors.loadConfig'), 'error')
      }
    } finally {
      loadingConfig.value = false
    }
  }

  // Config display sections (data-driven template)
  const configSections = computed(() => [
    {
      key: 'otd', icon: 'mdi-truck-delivery', titleKey: 'admin.clientConfig.sections.otd',
      fields: [
        { configKey: 'otd_mode', labelKey: 'admin.clientConfig.fields.otdMode',
          getValue: (cfg, defaults) => cfg.config?.otd_mode || defaults?.otd_mode,
          getIsDefault: (cfg) => !cfg.config?.otd_mode }
      ]
    },
    {
      key: 'efficiency', icon: 'mdi-speedometer', titleKey: 'admin.clientConfig.sections.efficiency',
      fields: [
        { configKey: 'default_cycle_time_hours', labelKey: 'admin.clientConfig.fields.defaultCycleTime',
          getValue: (cfg) => formatValue('default_cycle_time_hours', cfg.config?.default_cycle_time_hours) },
        { configKey: 'efficiency_target_percent', labelKey: 'admin.clientConfig.fields.efficiencyTarget',
          getValue: (cfg) => formatValue('efficiency_target_percent', cfg.config?.efficiency_target_percent) }
      ]
    },
    {
      key: 'quality', icon: 'mdi-check-decagram', titleKey: 'admin.clientConfig.sections.quality',
      fields: [
        { configKey: 'quality_target_ppm', labelKey: 'admin.clientConfig.fields.qualityTargetPpm',
          getValue: (cfg) => formatValue('quality_target_ppm', cfg.config?.quality_target_ppm) },
        { configKey: 'fpy_target_percent', labelKey: 'admin.clientConfig.fields.fpyTarget',
          getValue: (cfg) => formatValue('fpy_target_percent', cfg.config?.fpy_target_percent) },
        { configKey: 'dpmo_opportunities_default', labelKey: 'admin.clientConfig.fields.dpmoOpportunities',
          getValue: (cfg) => cfg.config?.dpmo_opportunities_default }
      ]
    },
    {
      key: 'oee', icon: 'mdi-chart-line', titleKey: 'admin.clientConfig.sections.oee',
      fields: [
        { configKey: 'availability_target_percent', labelKey: 'admin.clientConfig.fields.availabilityTarget',
          getValue: (cfg) => formatValue('availability_target_percent', cfg.config?.availability_target_percent) },
        { configKey: 'performance_target_percent', labelKey: 'admin.clientConfig.fields.performanceTarget',
          getValue: (cfg) => formatValue('performance_target_percent', cfg.config?.performance_target_percent) },
        { configKey: 'oee_target_percent', labelKey: 'admin.clientConfig.fields.oeeTarget',
          getValue: (cfg) => formatValue('oee_target_percent', cfg.config?.oee_target_percent) }
      ]
    },
    {
      key: 'wipAging', icon: 'mdi-clock-alert', titleKey: 'admin.clientConfig.sections.wipAging',
      fields: [
        { configKey: 'wip_aging_threshold_days', labelKey: 'admin.clientConfig.fields.wipAgingThreshold',
          getValue: (cfg) => formatValue('wip_aging_threshold_days', cfg.config?.wip_aging_threshold_days) },
        { configKey: 'wip_critical_threshold_days', labelKey: 'admin.clientConfig.fields.wipCriticalThreshold',
          getValue: (cfg) => formatValue('wip_critical_threshold_days', cfg.config?.wip_critical_threshold_days) },
        { configKey: 'absenteeism_target_percent', labelKey: 'admin.clientConfig.fields.absenteeismTarget',
          getValue: (cfg) => formatValue('absenteeism_target_percent', cfg.config?.absenteeism_target_percent) }
      ]
    }
  ])

  const initialize = async () => {
    await Promise.all([loadClients(), loadGlobalDefaults()])
  }

  return {
    // State
    loadingClients,
    loadingConfig,
    clients,
    selectedClientId,
    clientConfig,
    globalDefaults,
    snackbar,
    // Computed
    selectedClientName,
    // Display config
    configSections,
    // Methods
    formatLabel,
    formatValue,
    showSnackbar,
    loadClients,
    loadGlobalDefaults,
    loadClientConfig,
    initialize
  }
}
