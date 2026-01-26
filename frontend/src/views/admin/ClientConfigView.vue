<template>
  <v-container fluid>
    <v-row>
      <v-col cols="12">
        <div class="d-flex align-center justify-space-between mb-4">
          <h1 class="text-h4">
            <v-icon class="mr-2">mdi-cog-outline</v-icon>
            {{ $t('admin.clientConfig.title') }}
          </h1>
        </div>
        <p class="text-body-2 text-medium-emphasis mb-4">
          {{ $t('admin.clientConfig.description') }}
        </p>
      </v-col>
    </v-row>

    <!-- Global Defaults Card -->
    <v-row class="mb-4">
      <v-col cols="12">
        <v-card>
          <v-card-title class="d-flex align-center">
            <v-icon class="mr-2" color="info">mdi-earth</v-icon>
            {{ $t('admin.clientConfig.globalDefaults') }}
            <v-spacer />
            <v-chip color="info" size="small">
              {{ $t('admin.clientConfig.systemDefaults') }}
            </v-chip>
          </v-card-title>
          <v-card-text v-if="globalDefaults">
            <v-row>
              <v-col cols="12" md="4" v-for="(value, key) in globalDefaults" :key="key">
                <div class="d-flex justify-space-between align-center pa-2 bg-grey-lighten-4 rounded">
                  <span class="text-body-2 font-weight-medium">{{ formatLabel(key) }}</span>
                  <v-chip size="small" color="grey">{{ formatValue(key, value) }}</v-chip>
                </div>
              </v-col>
            </v-row>
          </v-card-text>
          <v-card-text v-else>
            <v-progress-circular indeterminate size="24" />
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Client Selector -->
    <v-row class="mb-4">
      <v-col cols="12" md="6">
        <v-autocomplete
          v-model="selectedClientId"
          :items="clients"
          item-title="client_name"
          item-value="client_id"
          :label="$t('admin.clientConfig.selectClient')"
          prepend-inner-icon="mdi-domain"
          variant="outlined"
          density="comfortable"
          clearable
          :loading="loadingClients"
          @update:model-value="loadClientConfig"
        >
          <template v-slot:item="{ item, props }">
            <v-list-item v-bind="props">
              <template v-slot:prepend>
                <v-icon>mdi-domain</v-icon>
              </template>
              <v-list-item-subtitle>ID: {{ item.raw.client_id }}</v-list-item-subtitle>
            </v-list-item>
          </template>
        </v-autocomplete>
      </v-col>
      <v-col cols="12" md="6" class="d-flex align-center">
        <v-btn
          color="primary"
          :disabled="!selectedClientId"
          @click="openEditDialog"
          class="mr-2"
        >
          <v-icon left>mdi-pencil</v-icon>
          {{ clientConfig && !clientConfig.is_default ? $t('common.edit') : $t('admin.clientConfig.createConfig') }}
        </v-btn>
        <v-btn
          v-if="clientConfig && !clientConfig.is_default"
          color="warning"
          variant="outlined"
          @click="confirmResetToDefaults"
        >
          <v-icon left>mdi-restore</v-icon>
          {{ $t('admin.clientConfig.resetToDefaults') }}
        </v-btn>
      </v-col>
    </v-row>

    <!-- Client Config Display -->
    <v-row v-if="selectedClientId">
      <v-col cols="12">
        <v-card :loading="loadingConfig">
          <v-card-title class="d-flex align-center">
            <v-icon class="mr-2" :color="clientConfig?.is_default ? 'grey' : 'success'">
              {{ clientConfig?.is_default ? 'mdi-cog' : 'mdi-cog-sync' }}
            </v-icon>
            {{ $t('admin.clientConfig.configFor') }}: {{ selectedClientName }}
            <v-spacer />
            <v-chip :color="clientConfig?.is_default ? 'grey' : 'success'" size="small">
              {{ clientConfig?.is_default ? $t('admin.clientConfig.usingDefaults') : $t('admin.clientConfig.customConfig') }}
            </v-chip>
          </v-card-title>

          <v-card-text v-if="clientConfig">
            <!-- OTD Configuration -->
            <h3 class="text-subtitle-1 font-weight-bold mb-3">
              <v-icon class="mr-1" size="small">mdi-truck-delivery</v-icon>
              {{ $t('admin.clientConfig.sections.otd') }}
            </h3>
            <v-row class="mb-4">
              <v-col cols="12" md="4">
                <ConfigValueCard
                  :label="$t('admin.clientConfig.fields.otdMode')"
                  :value="clientConfig.config?.otd_mode || globalDefaults?.otd_mode"
                  :is-default="!clientConfig.config?.otd_mode"
                />
              </v-col>
            </v-row>

            <!-- Efficiency Configuration -->
            <h3 class="text-subtitle-1 font-weight-bold mb-3">
              <v-icon class="mr-1" size="small">mdi-speedometer</v-icon>
              {{ $t('admin.clientConfig.sections.efficiency') }}
            </h3>
            <v-row class="mb-4">
              <v-col cols="12" md="4">
                <ConfigValueCard
                  :label="$t('admin.clientConfig.fields.defaultCycleTime')"
                  :value="formatValue('default_cycle_time_hours', clientConfig.config?.default_cycle_time_hours)"
                  :is-default="clientConfig.is_default"
                />
              </v-col>
              <v-col cols="12" md="4">
                <ConfigValueCard
                  :label="$t('admin.clientConfig.fields.efficiencyTarget')"
                  :value="formatValue('efficiency_target_percent', clientConfig.config?.efficiency_target_percent)"
                  :is-default="clientConfig.is_default"
                />
              </v-col>
            </v-row>

            <!-- Quality Configuration -->
            <h3 class="text-subtitle-1 font-weight-bold mb-3">
              <v-icon class="mr-1" size="small">mdi-check-decagram</v-icon>
              {{ $t('admin.clientConfig.sections.quality') }}
            </h3>
            <v-row class="mb-4">
              <v-col cols="12" md="4">
                <ConfigValueCard
                  :label="$t('admin.clientConfig.fields.qualityTargetPpm')"
                  :value="formatValue('quality_target_ppm', clientConfig.config?.quality_target_ppm)"
                  :is-default="clientConfig.is_default"
                />
              </v-col>
              <v-col cols="12" md="4">
                <ConfigValueCard
                  :label="$t('admin.clientConfig.fields.fpyTarget')"
                  :value="formatValue('fpy_target_percent', clientConfig.config?.fpy_target_percent)"
                  :is-default="clientConfig.is_default"
                />
              </v-col>
              <v-col cols="12" md="4">
                <ConfigValueCard
                  :label="$t('admin.clientConfig.fields.dpmoOpportunities')"
                  :value="clientConfig.config?.dpmo_opportunities_default"
                  :is-default="clientConfig.is_default"
                />
              </v-col>
            </v-row>

            <!-- OEE Configuration -->
            <h3 class="text-subtitle-1 font-weight-bold mb-3">
              <v-icon class="mr-1" size="small">mdi-chart-line</v-icon>
              {{ $t('admin.clientConfig.sections.oee') }}
            </h3>
            <v-row class="mb-4">
              <v-col cols="12" md="4">
                <ConfigValueCard
                  :label="$t('admin.clientConfig.fields.availabilityTarget')"
                  :value="formatValue('availability_target_percent', clientConfig.config?.availability_target_percent)"
                  :is-default="clientConfig.is_default"
                />
              </v-col>
              <v-col cols="12" md="4">
                <ConfigValueCard
                  :label="$t('admin.clientConfig.fields.performanceTarget')"
                  :value="formatValue('performance_target_percent', clientConfig.config?.performance_target_percent)"
                  :is-default="clientConfig.is_default"
                />
              </v-col>
              <v-col cols="12" md="4">
                <ConfigValueCard
                  :label="$t('admin.clientConfig.fields.oeeTarget')"
                  :value="formatValue('oee_target_percent', clientConfig.config?.oee_target_percent)"
                  :is-default="clientConfig.is_default"
                />
              </v-col>
            </v-row>

            <!-- WIP Aging Configuration -->
            <h3 class="text-subtitle-1 font-weight-bold mb-3">
              <v-icon class="mr-1" size="small">mdi-clock-alert</v-icon>
              {{ $t('admin.clientConfig.sections.wipAging') }}
            </h3>
            <v-row class="mb-4">
              <v-col cols="12" md="4">
                <ConfigValueCard
                  :label="$t('admin.clientConfig.fields.wipAgingThreshold')"
                  :value="formatValue('wip_aging_threshold_days', clientConfig.config?.wip_aging_threshold_days)"
                  :is-default="clientConfig.is_default"
                />
              </v-col>
              <v-col cols="12" md="4">
                <ConfigValueCard
                  :label="$t('admin.clientConfig.fields.wipCriticalThreshold')"
                  :value="formatValue('wip_critical_threshold_days', clientConfig.config?.wip_critical_threshold_days)"
                  :is-default="clientConfig.is_default"
                />
              </v-col>
              <v-col cols="12" md="4">
                <ConfigValueCard
                  :label="$t('admin.clientConfig.fields.absenteeismTarget')"
                  :value="formatValue('absenteeism_target_percent', clientConfig.config?.absenteeism_target_percent)"
                  :is-default="clientConfig.is_default"
                />
              </v-col>
            </v-row>
          </v-card-text>

          <v-card-text v-else-if="!loadingConfig">
            <v-alert type="info" variant="tonal">
              {{ $t('admin.clientConfig.selectClientPrompt') }}
            </v-alert>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Edit Dialog -->
    <v-dialog v-model="editDialog" max-width="800" persistent>
      <v-card>
        <v-card-title>
          <v-icon class="mr-2">mdi-pencil</v-icon>
          {{ $t('admin.clientConfig.editConfig') }}: {{ selectedClientName }}
        </v-card-title>
        <v-card-text>
          <v-form ref="configForm" v-model="formValid">
            <v-row>
              <!-- OTD Mode -->
              <v-col cols="12" md="6">
                <v-select
                  v-model="formData.otd_mode"
                  :items="otdModeOptions"
                  :label="$t('admin.clientConfig.fields.otdMode')"
                  prepend-icon="mdi-truck-delivery"
                  variant="outlined"
                  density="comfortable"
                  :hint="$t('admin.clientConfig.hints.otdMode')"
                  persistent-hint
                />
              </v-col>

              <!-- Default Cycle Time -->
              <v-col cols="12" md="6">
                <v-text-field
                  v-model.number="formData.default_cycle_time_hours"
                  :label="$t('admin.clientConfig.fields.defaultCycleTime')"
                  prepend-icon="mdi-timer"
                  type="number"
                  step="0.01"
                  min="0.01"
                  max="24"
                  variant="outlined"
                  density="comfortable"
                  :rules="[rules.required, rules.positiveNumber]"
                  suffix="hours"
                />
              </v-col>

              <!-- Efficiency Target -->
              <v-col cols="12" md="6">
                <v-text-field
                  v-model.number="formData.efficiency_target_percent"
                  :label="$t('admin.clientConfig.fields.efficiencyTarget')"
                  prepend-icon="mdi-speedometer"
                  type="number"
                  step="0.1"
                  min="0"
                  max="100"
                  variant="outlined"
                  density="comfortable"
                  :rules="[rules.required, rules.percentage]"
                  suffix="%"
                />
              </v-col>

              <!-- Quality Target PPM -->
              <v-col cols="12" md="6">
                <v-text-field
                  v-model.number="formData.quality_target_ppm"
                  :label="$t('admin.clientConfig.fields.qualityTargetPpm')"
                  prepend-icon="mdi-target"
                  type="number"
                  step="100"
                  min="0"
                  variant="outlined"
                  density="comfortable"
                  :rules="[rules.required, rules.positiveNumber]"
                  suffix="PPM"
                />
              </v-col>

              <!-- FPY Target -->
              <v-col cols="12" md="6">
                <v-text-field
                  v-model.number="formData.fpy_target_percent"
                  :label="$t('admin.clientConfig.fields.fpyTarget')"
                  prepend-icon="mdi-check-decagram"
                  type="number"
                  step="0.1"
                  min="0"
                  max="100"
                  variant="outlined"
                  density="comfortable"
                  :rules="[rules.required, rules.percentage]"
                  suffix="%"
                />
              </v-col>

              <!-- DPMO Opportunities -->
              <v-col cols="12" md="6">
                <v-text-field
                  v-model.number="formData.dpmo_opportunities_default"
                  :label="$t('admin.clientConfig.fields.dpmoOpportunities')"
                  prepend-icon="mdi-numeric"
                  type="number"
                  step="1"
                  min="1"
                  variant="outlined"
                  density="comfortable"
                  :rules="[rules.required, rules.positiveInteger]"
                />
              </v-col>

              <!-- Availability Target -->
              <v-col cols="12" md="4">
                <v-text-field
                  v-model.number="formData.availability_target_percent"
                  :label="$t('admin.clientConfig.fields.availabilityTarget')"
                  prepend-icon="mdi-power"
                  type="number"
                  step="0.1"
                  min="0"
                  max="100"
                  variant="outlined"
                  density="comfortable"
                  :rules="[rules.required, rules.percentage]"
                  suffix="%"
                />
              </v-col>

              <!-- Performance Target -->
              <v-col cols="12" md="4">
                <v-text-field
                  v-model.number="formData.performance_target_percent"
                  :label="$t('admin.clientConfig.fields.performanceTarget')"
                  prepend-icon="mdi-rocket"
                  type="number"
                  step="0.1"
                  min="0"
                  max="100"
                  variant="outlined"
                  density="comfortable"
                  :rules="[rules.required, rules.percentage]"
                  suffix="%"
                />
              </v-col>

              <!-- OEE Target -->
              <v-col cols="12" md="4">
                <v-text-field
                  v-model.number="formData.oee_target_percent"
                  :label="$t('admin.clientConfig.fields.oeeTarget')"
                  prepend-icon="mdi-chart-line"
                  type="number"
                  step="0.1"
                  min="0"
                  max="100"
                  variant="outlined"
                  density="comfortable"
                  :rules="[rules.required, rules.percentage]"
                  suffix="%"
                />
              </v-col>

              <!-- Absenteeism Target -->
              <v-col cols="12" md="4">
                <v-text-field
                  v-model.number="formData.absenteeism_target_percent"
                  :label="$t('admin.clientConfig.fields.absenteeismTarget')"
                  prepend-icon="mdi-account-off"
                  type="number"
                  step="0.1"
                  min="0"
                  max="100"
                  variant="outlined"
                  density="comfortable"
                  :rules="[rules.required, rules.percentage]"
                  suffix="%"
                />
              </v-col>

              <!-- WIP Aging Threshold -->
              <v-col cols="12" md="4">
                <v-text-field
                  v-model.number="formData.wip_aging_threshold_days"
                  :label="$t('admin.clientConfig.fields.wipAgingThreshold')"
                  prepend-icon="mdi-clock-alert"
                  type="number"
                  step="1"
                  min="1"
                  variant="outlined"
                  density="comfortable"
                  :rules="[rules.required, rules.positiveInteger]"
                  suffix="days"
                />
              </v-col>

              <!-- WIP Critical Threshold -->
              <v-col cols="12" md="4">
                <v-text-field
                  v-model.number="formData.wip_critical_threshold_days"
                  :label="$t('admin.clientConfig.fields.wipCriticalThreshold')"
                  prepend-icon="mdi-alert-circle"
                  type="number"
                  step="1"
                  min="1"
                  variant="outlined"
                  density="comfortable"
                  :rules="[rules.required, rules.positiveInteger]"
                  suffix="days"
                />
              </v-col>
            </v-row>
          </v-form>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="editDialog = false">{{ $t('common.cancel') }}</v-btn>
          <v-btn color="primary" :loading="saving" :disabled="!formValid" @click="saveConfig">
            {{ $t('common.save') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Confirm Reset Dialog -->
    <v-dialog v-model="confirmResetDialog" max-width="400">
      <v-card>
        <v-card-title class="text-warning">
          <v-icon class="mr-2" color="warning">mdi-alert</v-icon>
          {{ $t('admin.clientConfig.confirmReset') }}
        </v-card-title>
        <v-card-text>
          {{ $t('admin.clientConfig.confirmResetMessage', { client: selectedClientName }) }}
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="confirmResetDialog = false">{{ $t('common.cancel') }}</v-btn>
          <v-btn color="warning" :loading="resetting" @click="resetToDefaults">
            {{ $t('admin.clientConfig.reset') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Snackbar -->
    <v-snackbar v-model="snackbar.show" :color="snackbar.color" :timeout="3000">
      {{ snackbar.text }}
    </v-snackbar>
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/services/api'

const { t } = useI18n()

// Simple ConfigValueCard component inline
const ConfigValueCard = {
  props: {
    label: String,
    value: [String, Number],
    isDefault: Boolean
  },
  template: `
    <div class="d-flex justify-space-between align-center pa-3 rounded" :class="isDefault ? 'bg-grey-lighten-4' : 'bg-success-lighten-5'">
      <span class="text-body-2">{{ label }}</span>
      <v-chip :size="'small'" :color="isDefault ? 'grey' : 'success'">{{ value }}</v-chip>
    </div>
  `
}

// State
const loadingClients = ref(false)
const loadingConfig = ref(false)
const saving = ref(false)
const resetting = ref(false)

const clients = ref([])
const selectedClientId = ref(null)
const clientConfig = ref(null)
const globalDefaults = ref(null)

const editDialog = ref(false)
const confirmResetDialog = ref(false)
const formValid = ref(false)
const configForm = ref(null)

const snackbar = ref({ show: false, text: '', color: 'success' })

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

// Computed
const selectedClientName = computed(() => {
  const client = clients.value.find(c => c.client_id === selectedClientId.value)
  return client?.client_name || selectedClientId.value
})

// Methods
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

const loadClients = async () => {
  loadingClients.value = true
  try {
    const response = await api.get('/api/clients')
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

const openEditDialog = () => {
  if (clientConfig.value?.config) {
    formData.value = { ...clientConfig.value.config }
  } else if (globalDefaults.value) {
    formData.value = { ...globalDefaults.value }
  }
  editDialog.value = true
}

const saveConfig = async () => {
  if (!configForm.value?.validate()) return

  saving.value = true
  try {
    if (clientConfig.value?.is_default) {
      // Create new config
      await api.post('/client-config/', {
        client_id: selectedClientId.value,
        ...formData.value
      })
      showSnackbar(t('admin.clientConfig.success.created'), 'success')
    } else {
      // Update existing config
      await api.put(`/client-config/${selectedClientId.value}`, formData.value)
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

const confirmResetToDefaults = () => {
  confirmResetDialog.value = true
}

const resetToDefaults = async () => {
  resetting.value = true
  try {
    await api.post(`/client-config/${selectedClientId.value}/reset-to-defaults`)
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

const showSnackbar = (text, color) => {
  snackbar.value = { show: true, text, color }
}

// Lifecycle
onMounted(async () => {
  await Promise.all([loadClients(), loadGlobalDefaults()])
})
</script>

<style scoped>
.bg-success-lighten-5 {
  background-color: rgba(76, 175, 80, 0.08);
}
</style>
