/**
 * Composable for Client Config form state, validation, and submission.
 * Handles: edit dialog, reset dialog, form data, validation rules, save/reset operations.
 */
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/services/api'

export function useClientConfigForms(getSelectedClientId, getClientConfig, getGlobalDefaults, showSnackbar, loadClientConfig) {
  const { t } = useI18n()

  // Dialog states
  const editDialog = ref(false)
  const confirmResetDialog = ref(false)
  const formValid = ref(false)
  const configForm = ref(null)
  const saving = ref(false)
  const resetting = ref(false)

  // Form data
  const formData = ref({
    otd_mode: 'STANDARD',
    default_cycle_time_hours: 0.25,
    efficiency_target_percent: 85.0,
    quality_target_ppm: 10000.0,
    fpy_target_percent: 95.0,
    dpmo_opportunities_default: 1,
    availability_target_percent: 90.0,
    performance_target_percent: 95.0,
    oee_target_percent: 85.0,
    absenteeism_target_percent: 3.0,
    wip_aging_threshold_days: 7,
    wip_critical_threshold_days: 14
  })

  // Options
  const otdModeOptions = [
    { title: 'Standard OTD', value: 'STANDARD' },
    { title: 'True OTD (Complete Orders Only)', value: 'TRUE' },
    { title: 'Both (Show Standard & True)', value: 'BOTH' }
  ]

  // Validation rules
  const rules = {
    required: v => !!v || v === 0 || t('validation.required'),
    positiveNumber: v => v > 0 || t('validation.positiveNumber'),
    positiveInteger: v => (Number.isInteger(v) && v > 0) || t('validation.positiveInteger'),
    percentage: v => (v >= 0 && v <= 100) || t('validation.percentage')
  }

  // Edit form field definitions (data-driven template)
  const editFormFields = [
    { key: 'otd_mode', type: 'select', labelKey: 'admin.clientConfig.fields.otdMode', icon: 'mdi-truck-delivery', items: otdModeOptions, hintKey: 'admin.clientConfig.hints.otdMode', md: 6 },
    { key: 'default_cycle_time_hours', labelKey: 'admin.clientConfig.fields.defaultCycleTime', icon: 'mdi-timer', step: 0.01, min: 0.01, max: 24, suffix: 'hours', rules: ['required', 'positiveNumber'], md: 6 },
    { key: 'efficiency_target_percent', labelKey: 'admin.clientConfig.fields.efficiencyTarget', icon: 'mdi-speedometer', step: 0.1, min: 0, max: 100, suffix: '%', rules: ['required', 'percentage'], md: 6 },
    { key: 'quality_target_ppm', labelKey: 'admin.clientConfig.fields.qualityTargetPpm', icon: 'mdi-target', step: 100, min: 0, suffix: 'PPM', rules: ['required', 'positiveNumber'], md: 6 },
    { key: 'fpy_target_percent', labelKey: 'admin.clientConfig.fields.fpyTarget', icon: 'mdi-check-decagram', step: 0.1, min: 0, max: 100, suffix: '%', rules: ['required', 'percentage'], md: 6 },
    { key: 'dpmo_opportunities_default', labelKey: 'admin.clientConfig.fields.dpmoOpportunities', icon: 'mdi-numeric', step: 1, min: 1, rules: ['required', 'positiveInteger'], md: 6 },
    { key: 'availability_target_percent', labelKey: 'admin.clientConfig.fields.availabilityTarget', icon: 'mdi-power', step: 0.1, min: 0, max: 100, suffix: '%', rules: ['required', 'percentage'], md: 4 },
    { key: 'performance_target_percent', labelKey: 'admin.clientConfig.fields.performanceTarget', icon: 'mdi-rocket', step: 0.1, min: 0, max: 100, suffix: '%', rules: ['required', 'percentage'], md: 4 },
    { key: 'oee_target_percent', labelKey: 'admin.clientConfig.fields.oeeTarget', icon: 'mdi-chart-line', step: 0.1, min: 0, max: 100, suffix: '%', rules: ['required', 'percentage'], md: 4 },
    { key: 'absenteeism_target_percent', labelKey: 'admin.clientConfig.fields.absenteeismTarget', icon: 'mdi-account-off', step: 0.1, min: 0, max: 100, suffix: '%', rules: ['required', 'percentage'], md: 4 },
    { key: 'wip_aging_threshold_days', labelKey: 'admin.clientConfig.fields.wipAgingThreshold', icon: 'mdi-clock-alert', step: 1, min: 1, suffix: 'days', rules: ['required', 'positiveInteger'], md: 4 },
    { key: 'wip_critical_threshold_days', labelKey: 'admin.clientConfig.fields.wipCriticalThreshold', icon: 'mdi-alert-circle', step: 1, min: 1, suffix: 'days', rules: ['required', 'positiveInteger'], md: 4 }
  ]

  // Dialog actions
  const openEditDialog = () => {
    const config = getClientConfig()
    const defaults = getGlobalDefaults()
    if (config?.config) {
      formData.value = { ...config.config }
    } else if (defaults) {
      formData.value = { ...defaults }
    }
    editDialog.value = true
  }

  const confirmResetToDefaults = () => {
    confirmResetDialog.value = true
  }

  // Submission
  const saveConfig = async () => {
    if (!configForm.value?.validate()) return

    saving.value = true
    try {
      const clientId = getSelectedClientId()
      const config = getClientConfig()
      if (config?.is_default) {
        // Create new config
        await api.post('/client-config/', {
          client_id: clientId,
          ...formData.value
        })
        showSnackbar(t('admin.clientConfig.success.created'), 'success')
      } else {
        // Update existing config
        await api.put(`/client-config/${clientId}`, formData.value)
        showSnackbar(t('admin.clientConfig.success.updated'), 'success')
      }
      editDialog.value = false
      await loadClientConfig()
    } catch (error) {
      console.error('Failed to save config:', error)
      showSnackbar(t('admin.clientConfig.errors.save'), 'error')
    } finally {
      saving.value = false
    }
  }

  const resetToDefaults = async () => {
    resetting.value = true
    try {
      const clientId = getSelectedClientId()
      await api.post(`/client-config/${clientId}/reset-to-defaults`)
      showSnackbar(t('admin.clientConfig.success.reset'), 'success')
      confirmResetDialog.value = false
      await loadClientConfig()
    } catch (error) {
      console.error('Failed to reset config:', error)
      showSnackbar(t('admin.clientConfig.errors.reset'), 'error')
    } finally {
      resetting.value = false
    }
  }

  return {
    // Dialog states
    editDialog,
    confirmResetDialog,
    formValid,
    configForm,
    saving,
    resetting,
    // Form data
    formData,
    // Options & rules
    otdModeOptions,
    rules,
    // Form field definitions
    editFormFields,
    // Methods
    openEditDialog,
    confirmResetToDefaults,
    saveConfig,
    resetToDefaults
  }
}
