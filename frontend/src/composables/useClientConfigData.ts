/**
 * Composable for Client Config data fetching + display logic.
 * Clients list, global defaults, per-client config, formatting.
 */
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/services/api'
import type { ClientConfigData, ClientConfigEnvelope } from './useClientConfigForms'

export interface ClientRow {
  client_id: string | number
  client_name?: string
  [key: string]: unknown
}

export interface SnackbarState {
  show: boolean
  text: string
  color: string
}

export interface ConfigSectionField {
  configKey: keyof ClientConfigData | string
  labelKey: string
  getValue: (cfg: ClientConfigEnvelope, defaults: ClientConfigData | null) => unknown
  getIsDefault?: (cfg: ClientConfigEnvelope) => boolean
}

export interface ConfigSection {
  key: string
  icon: string
  titleKey: string
  fields: ConfigSectionField[]
}

export function useClientConfigData() {
  const { t } = useI18n()

  const loadingClients = ref(false)
  const loadingConfig = ref(false)

  const clients = ref<ClientRow[]>([])
  const selectedClientId = ref<string | number | null>(null)
  const clientConfig = ref<ClientConfigEnvelope | null>(null)
  const globalDefaults = ref<ClientConfigData | null>(null)

  const snackbar = ref<SnackbarState>({ show: false, text: '', color: 'success' })

  const selectedClientName = computed<string | number | null>(() => {
    const client = clients.value.find((c) => c.client_id === selectedClientId.value)
    return client?.client_name || selectedClientId.value
  })

  const formatLabel = (key: string): string =>
    key.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())

  const formatValue = (key: string, value: unknown): string => {
    if (value === null || value === undefined) return '-'
    if (key.includes('percent')) return `${value}%`
    if (key.includes('hours')) return `${value} hrs`
    if (key.includes('days')) return `${value} days`
    if (key.includes('ppm') && typeof value === 'number') return `${value.toLocaleString()} PPM`
    return String(value)
  }

  const showSnackbar = (text: string, color: string): void => {
    snackbar.value = { show: true, text, color }
  }

  const loadClients = async (): Promise<void> => {
    loadingClients.value = true
    try {
      const response = await api.get('/clients')
      clients.value = response.data
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to load clients:', error)
      showSnackbar(t('admin.clientConfig.errors.loadClients'), 'error')
    } finally {
      loadingClients.value = false
    }
  }

  const loadGlobalDefaults = async (): Promise<void> => {
    try {
      const response = await api.get('/client-config/defaults')
      globalDefaults.value = response.data as ClientConfigData
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to load global defaults:', error)
    }
  }

  const loadClientConfig = async (): Promise<void> => {
    if (!selectedClientId.value) {
      clientConfig.value = null
      return
    }

    loadingConfig.value = true
    try {
      const response = await api.get(`/client-config/${selectedClientId.value}`)
      clientConfig.value = response.data as ClientConfigEnvelope
    } catch (error) {
      const ax = error as { response?: { status?: number } }
      if (ax?.response?.status === 404) {
        clientConfig.value = {
          is_default: true,
          config: { ...(globalDefaults.value || ({} as ClientConfigData)) },
        }
      } else {
        // eslint-disable-next-line no-console
        console.error('Failed to load client config:', error)
        showSnackbar(t('admin.clientConfig.errors.loadConfig'), 'error')
      }
    } finally {
      loadingConfig.value = false
    }
  }

  const configSections = computed<ConfigSection[]>(() => [
    {
      key: 'otd',
      icon: 'mdi-truck-delivery',
      titleKey: 'admin.clientConfig.sections.otd',
      fields: [
        {
          configKey: 'otd_mode',
          labelKey: 'admin.clientConfig.fields.otdMode',
          getValue: (cfg, defaults) =>
            cfg.config?.otd_mode || defaults?.otd_mode,
          getIsDefault: (cfg) => !cfg.config?.otd_mode,
        },
      ],
    },
    {
      key: 'efficiency',
      icon: 'mdi-speedometer',
      titleKey: 'admin.clientConfig.sections.efficiency',
      fields: [
        {
          configKey: 'default_cycle_time_hours',
          labelKey: 'admin.clientConfig.fields.defaultCycleTime',
          getValue: (cfg) =>
            formatValue('default_cycle_time_hours', cfg.config?.default_cycle_time_hours),
        },
        {
          configKey: 'efficiency_target_percent',
          labelKey: 'admin.clientConfig.fields.efficiencyTarget',
          getValue: (cfg) =>
            formatValue('efficiency_target_percent', cfg.config?.efficiency_target_percent),
        },
      ],
    },
    {
      key: 'quality',
      icon: 'mdi-check-decagram',
      titleKey: 'admin.clientConfig.sections.quality',
      fields: [
        {
          configKey: 'quality_target_ppm',
          labelKey: 'admin.clientConfig.fields.qualityTargetPpm',
          getValue: (cfg) =>
            formatValue('quality_target_ppm', cfg.config?.quality_target_ppm),
        },
        {
          configKey: 'fpy_target_percent',
          labelKey: 'admin.clientConfig.fields.fpyTarget',
          getValue: (cfg) =>
            formatValue('fpy_target_percent', cfg.config?.fpy_target_percent),
        },
        {
          configKey: 'dpmo_opportunities_default',
          labelKey: 'admin.clientConfig.fields.dpmoOpportunities',
          getValue: (cfg) => cfg.config?.dpmo_opportunities_default,
        },
      ],
    },
    {
      key: 'oee',
      icon: 'mdi-chart-line',
      titleKey: 'admin.clientConfig.sections.oee',
      fields: [
        {
          configKey: 'availability_target_percent',
          labelKey: 'admin.clientConfig.fields.availabilityTarget',
          getValue: (cfg) =>
            formatValue(
              'availability_target_percent',
              cfg.config?.availability_target_percent,
            ),
        },
        {
          configKey: 'performance_target_percent',
          labelKey: 'admin.clientConfig.fields.performanceTarget',
          getValue: (cfg) =>
            formatValue(
              'performance_target_percent',
              cfg.config?.performance_target_percent,
            ),
        },
        {
          configKey: 'oee_target_percent',
          labelKey: 'admin.clientConfig.fields.oeeTarget',
          getValue: (cfg) =>
            formatValue('oee_target_percent', cfg.config?.oee_target_percent),
        },
      ],
    },
    {
      key: 'wipAging',
      icon: 'mdi-clock-alert',
      titleKey: 'admin.clientConfig.sections.wipAging',
      fields: [
        {
          configKey: 'wip_aging_threshold_days',
          labelKey: 'admin.clientConfig.fields.wipAgingThreshold',
          getValue: (cfg) =>
            formatValue('wip_aging_threshold_days', cfg.config?.wip_aging_threshold_days),
        },
        {
          configKey: 'wip_critical_threshold_days',
          labelKey: 'admin.clientConfig.fields.wipCriticalThreshold',
          getValue: (cfg) =>
            formatValue(
              'wip_critical_threshold_days',
              cfg.config?.wip_critical_threshold_days,
            ),
        },
        {
          configKey: 'absenteeism_target_percent',
          labelKey: 'admin.clientConfig.fields.absenteeismTarget',
          getValue: (cfg) =>
            formatValue(
              'absenteeism_target_percent',
              cfg.config?.absenteeism_target_percent,
            ),
        },
      ],
    },
  ])

  const initialize = async (): Promise<void> => {
    await Promise.all([loadClients(), loadGlobalDefaults()])
  }

  return {
    loadingClients,
    loadingConfig,
    clients,
    selectedClientId,
    clientConfig,
    globalDefaults,
    snackbar,
    selectedClientName,
    configSections,
    formatLabel,
    formatValue,
    showSnackbar,
    loadClients,
    loadGlobalDefaults,
    loadClientConfig,
    initialize,
  }
}
