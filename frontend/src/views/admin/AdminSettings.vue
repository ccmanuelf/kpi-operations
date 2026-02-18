<template>
  <v-container fluid>
    <v-row>
      <v-col cols="12">
        <h1 class="text-h4 mb-4">
          <v-icon class="mr-2">mdi-cog</v-icon>
          {{ t('admin.settings.title') }}
        </h1>
      </v-col>
    </v-row>

    <v-row>
      <!-- General Settings -->
      <v-col cols="12" md="6">
        <v-card>
          <v-card-title>
            <v-icon class="mr-2">mdi-tune</v-icon>
            {{ t('admin.settings.generalSettings') }}
          </v-card-title>
          <v-card-text>
            <v-form ref="generalForm">
              <v-text-field
                v-model="settings.companyName"
                :label="t('admin.settings.companyName')"
                prepend-icon="mdi-domain"
                variant="outlined"
                density="comfortable"
                class="mb-3"
              />
              <v-text-field
                v-model="settings.timezone"
                :label="t('admin.settings.timezone')"
                prepend-icon="mdi-clock-outline"
                variant="outlined"
                density="comfortable"
                class="mb-3"
              />
              <v-select
                v-model="settings.dateFormat"
                :items="dateFormats"
                :label="t('admin.settings.dateFormat')"
                prepend-icon="mdi-calendar"
                variant="outlined"
                density="comfortable"
                class="mb-3"
              />
              <v-select
                v-model="settings.language"
                :items="languages"
                :label="t('admin.settings.language')"
                prepend-icon="mdi-translate"
                variant="outlined"
                density="comfortable"
              />
            </v-form>
          </v-card-text>
          <v-card-actions>
            <v-spacer />
            <v-btn color="primary" @click="saveGeneralSettings" :loading="saving">
              {{ t('admin.settings.saveChanges') }}
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-col>

      <!-- KPI Thresholds -->
      <v-col cols="12" md="6">
        <v-card>
          <v-card-title class="d-flex align-center">
            <v-icon class="mr-2">mdi-chart-line</v-icon>
            <span>{{ t('admin.settings.kpiThresholds') }}</span>
            <v-spacer />
            <v-chip v-if="selectedClientId" color="primary" size="small" class="ml-2">
              {{ selectedClientName }}
            </v-chip>
            <v-chip v-else color="grey" size="small" class="ml-2">
              {{ t('admin.settings.globalDefaults') }}
            </v-chip>
          </v-card-title>
          <v-card-text>
            <!-- Client Selector -->
            <v-select
              v-model="selectedClientId"
              :items="clientOptions"
              item-title="name"
              item-value="id"
              :label="t('admin.settings.selectClientOrGlobal')"
              prepend-icon="mdi-domain"
              variant="outlined"
              density="comfortable"
              class="mb-4"
              clearable
              @update:model-value="loadThresholds"
            />

            <v-divider class="mb-4" />

            <!-- Loading state -->
            <div v-if="loadingThresholds" class="text-center py-4">
              <v-progress-circular indeterminate color="primary" />
              <div class="text-grey mt-2">{{ t('admin.settings.loadingThresholds') }}</div>
            </div>

            <!-- Thresholds Form -->
            <v-form v-else ref="thresholdsForm">
              <v-row dense>
                <v-col cols="12" sm="6" v-for="kpi in kpiList" :key="kpi.key">
                  <v-text-field
                    v-model.number="thresholds[kpi.key]"
                    :label="kpi.label"
                    :prepend-icon="kpi.icon"
                    :suffix="kpi.unit"
                    type="number"
                    variant="outlined"
                    density="compact"
                    :hint="getThresholdHint(kpi.key)"
                    persistent-hint
                  />
                </v-col>
              </v-row>

              <!-- Info about inheritance -->
              <v-alert
                v-if="selectedClientId && hasGlobalOverrides"
                type="info"
                variant="tonal"
                density="compact"
                class="mt-4"
              >
                <template v-slot:prepend>
                  <v-icon>mdi-information</v-icon>
                </template>
                {{ t('admin.settings.clientOverrideHint') }}
              </v-alert>
            </v-form>
          </v-card-text>
          <v-card-actions>
            <v-btn
              v-if="selectedClientId"
              variant="outlined"
              color="secondary"
              @click="resetToGlobal"
              :disabled="!hasClientOverrides"
            >
              {{ t('admin.settings.resetToGlobal') }}
            </v-btn>
            <v-spacer />
            <v-btn color="primary" @click="saveThresholds" :loading="savingThresholds">
              {{ t('admin.settings.saveThresholds') }}
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-col>

      <!-- Notification Settings -->
      <v-col cols="12" md="6">
        <v-card>
          <v-card-title>
            <v-icon class="mr-2">mdi-bell</v-icon>
            {{ t('admin.settings.notifications') }}
          </v-card-title>
          <v-card-text>
            <v-switch
              v-model="settings.emailNotifications"
              :label="t('admin.settings.emailNotifications')"
              color="primary"
              class="mb-2"
            />
            <v-switch
              v-model="settings.alertOnThresholdBreach"
              :label="t('admin.settings.alertOnThresholdBreach')"
              color="primary"
              class="mb-2"
            />
            <v-switch
              v-model="settings.dailyReportEnabled"
              :label="t('admin.settings.dailySummaryReport')"
              color="primary"
              class="mb-2"
            />
            <v-text-field
              v-if="settings.dailyReportEnabled"
              v-model="settings.reportRecipients"
              :label="t('admin.settings.reportRecipients')"
              prepend-icon="mdi-email-multiple"
              variant="outlined"
              density="comfortable"
            />
          </v-card-text>
          <v-card-actions>
            <v-spacer />
            <v-btn color="primary" @click="saveNotificationSettings" :loading="saving">
              {{ t('admin.settings.saveNotifications') }}
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-col>

      <!-- Data Retention -->
      <v-col cols="12" md="6">
        <v-card>
          <v-card-title>
            <v-icon class="mr-2">mdi-database</v-icon>
            {{ t('admin.settings.dataManagement') }}
          </v-card-title>
          <v-card-text>
            <v-select
              v-model="settings.dataRetentionPeriod"
              :items="retentionPeriods"
              :label="t('admin.settings.dataRetentionPeriod')"
              prepend-icon="mdi-calendar-clock"
              variant="outlined"
              density="comfortable"
              class="mb-3"
            />
            <v-switch
              v-model="settings.autoBackup"
              :label="t('admin.settings.automaticBackups')"
              color="primary"
              class="mb-2"
            />
            <v-select
              v-if="settings.autoBackup"
              v-model="settings.backupFrequency"
              :items="backupFrequencies"
              :label="t('admin.settings.backupFrequency')"
              prepend-icon="mdi-backup-restore"
              variant="outlined"
              density="comfortable"
            />
          </v-card-text>
          <v-card-actions>
            <v-btn color="secondary" variant="outlined" @click="exportData">
              <v-icon left>mdi-download</v-icon>
              {{ t('admin.settings.exportData') }}
            </v-btn>
            <v-spacer />
            <v-btn color="primary" @click="saveDataSettings" :loading="saving">
              {{ t('admin.settings.saveSettings') }}
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-col>
    </v-row>

    <!-- Snackbar for notifications -->
    <v-snackbar v-model="snackbar" :color="snackbarColor" :timeout="3000">
      {{ snackbarMessage }}
    </v-snackbar>
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
import api from '@/services/api'

const saving = ref(false)
const savingThresholds = ref(false)
const loadingThresholds = ref(false)
const snackbar = ref(false)
const snackbarMessage = ref('')
const snackbarColor = ref('success')

// Client selection for thresholds
const clients = ref([])
const selectedClientId = ref(null)
const selectedClientName = computed(() => {
  const client = clients.value.find(c => c.client_id === selectedClientId.value)
  return client?.client_name || ''
})

const clientOptions = computed(() => {
  return [
    { id: null, name: t('admin.settings.globalDefaultsAll') },
    ...clients.value.map(c => ({ id: c.client_id, name: c.client_name }))
  ]
})

// KPI definitions
const kpiList = computed(() => [
  { key: 'efficiency', label: t('admin.settings.kpi.efficiencyTarget'), icon: 'mdi-speedometer', unit: '%' },
  { key: 'quality', label: t('admin.settings.kpi.qualityTarget'), icon: 'mdi-star', unit: '%' },
  { key: 'availability', label: t('admin.settings.kpi.availabilityTarget'), icon: 'mdi-server', unit: '%' },
  { key: 'performance', label: t('admin.settings.kpi.performanceTarget'), icon: 'mdi-gauge', unit: '%' },
  { key: 'oee', label: t('admin.settings.kpi.oeeTarget'), icon: 'mdi-factory', unit: '%' },
  { key: 'ppm', label: t('admin.settings.kpi.ppmTarget'), icon: 'mdi-alert-circle', unit: 'ppm' },
  { key: 'absenteeism', label: t('admin.settings.kpi.absenteeismTarget'), icon: 'mdi-account-alert', unit: '%' },
  { key: 'otd', label: t('admin.settings.kpi.otdTarget'), icon: 'mdi-truck-delivery', unit: '%' },
  { key: 'wip_aging', label: t('admin.settings.kpi.wipAgingTarget'), icon: 'mdi-clock-alert', unit: t('common.days') },
  { key: 'throughput', label: t('admin.settings.kpi.throughputTarget'), icon: 'mdi-timer', unit: t('admin.settings.kpi.hrs') }
])

// Thresholds state
const thresholds = ref({})
const originalThresholds = ref({})
const globalDefaults = ref({})

const hasClientOverrides = computed(() => {
  if (!selectedClientId.value) return false
  return Object.keys(thresholds.value).some(key => {
    const current = thresholds.value[key]
    const global = globalDefaults.value[key]
    return current !== global
  })
})

const hasGlobalOverrides = computed(() => {
  return Object.values(originalThresholds.value).some(t => !t.is_global)
})

const getThresholdHint = (key) => {
  const original = originalThresholds.value[key]
  if (!original) return ''
  if (selectedClientId.value && original.is_global) {
    return `${t('admin.settings.globalDefault')}: ${original.target_value}`
  }
  return ''
}

// General settings
const settings = ref({
  companyName: 'KPI Operations',
  timezone: 'America/Mexico_City',
  dateFormat: 'YYYY-MM-DD',
  language: 'en',
  emailNotifications: true,
  alertOnThresholdBreach: true,
  dailyReportEnabled: false,
  reportRecipients: '',
  dataRetentionPeriod: '1 year',
  autoBackup: true,
  backupFrequency: 'daily'
})

const dateFormats = ['YYYY-MM-DD', 'DD/MM/YYYY', 'MM/DD/YYYY', 'DD-MMM-YYYY']
const languages = computed(() => [
  { title: t('admin.settings.langEnglish'), value: 'en' },
  { title: t('admin.settings.langSpanish'), value: 'es' },
  { title: t('admin.settings.langFrench'), value: 'fr' }
])
const retentionPeriods = computed(() => [
  t('admin.settings.retention6Months'),
  t('admin.settings.retention1Year'),
  t('admin.settings.retention2Years'),
  t('admin.settings.retention5Years'),
  t('admin.settings.retentionForever')
])
const backupFrequencies = computed(() => [
  { title: t('admin.settings.freqDaily'), value: 'daily' },
  { title: t('admin.settings.freqWeekly'), value: 'weekly' },
  { title: t('admin.settings.freqMonthly'), value: 'monthly' }
])

const showSnackbar = (message, color = 'success') => {
  snackbarMessage.value = message
  snackbarColor.value = color
  snackbar.value = true
}

const loadClients = async () => {
  try {
    const response = await api.getClients()
    clients.value = response.data || []
  } catch (error) {
    console.error('Failed to load clients:', error)
  }
}

const loadThresholds = async () => {
  loadingThresholds.value = true
  try {
    const response = await api.getKPIThresholds(selectedClientId.value)
    const data = response.data

    // Store original data for comparison
    originalThresholds.value = data.thresholds || {}

    // Extract just the target values for the form
    thresholds.value = {}
    for (const [key, value] of Object.entries(data.thresholds || {})) {
      thresholds.value[key] = value.target_value
    }

    // Store global defaults for reference
    if (!selectedClientId.value) {
      globalDefaults.value = { ...thresholds.value }
    }
  } catch (error) {
    console.error('Failed to load thresholds:', error)
    showSnackbar(t('admin.settings.failedToLoad') + ' thresholds', 'error')
  } finally {
    loadingThresholds.value = false
  }
}

const saveThresholds = async () => {
  savingThresholds.value = true
  try {
    // Build thresholds object with only changed values
    const thresholdsToSave = {}
    for (const kpi of kpiList) {
      if (thresholds.value[kpi.key] !== undefined) {
        thresholdsToSave[kpi.key] = {
          target_value: thresholds.value[kpi.key]
        }
      }
    }

    await api.updateKPIThresholds({
      client_id: selectedClientId.value,
      thresholds: thresholdsToSave
    })

    showSnackbar(
      selectedClientId.value
        ? `${t('admin.settings.thresholdsSavedFor')} ${selectedClientName.value}`
        : t('admin.settings.globalThresholdsSaved')
    )

    // Reload to get updated data
    await loadThresholds()
  } catch (error) {
    showSnackbar(error.response?.data?.detail || t('admin.settings.failedToSave') + ' thresholds', 'error')
  } finally {
    savingThresholds.value = false
  }
}

const resetToGlobal = async () => {
  if (!selectedClientId.value) return

  try {
    // Delete all client-specific thresholds
    for (const kpi of kpiList) {
      const original = originalThresholds.value[kpi.key]
      if (original && !original.is_global) {
        await api.deleteClientThreshold(selectedClientId.value, kpi.key)
      }
    }

    showSnackbar(`${t('admin.settings.resetToGlobalSuccess')} - ${selectedClientName.value}`)
    await loadThresholds()
  } catch (error) {
    showSnackbar(t('admin.settings.failedToSave'), 'error')
  }
}

const saveGeneralSettings = async () => {
  saving.value = true
  try {
    await new Promise(resolve => setTimeout(resolve, 500))
    showSnackbar(t('admin.settings.generalSettingsSaved'))
  } catch (error) {
    showSnackbar(t('admin.settings.failedToSave'), 'error')
  } finally {
    saving.value = false
  }
}

const saveNotificationSettings = async () => {
  saving.value = true
  try {
    await new Promise(resolve => setTimeout(resolve, 500))
    showSnackbar(t('admin.settings.notificationSettingsSaved'))
  } catch (error) {
    showSnackbar(t('admin.settings.failedToSave'), 'error')
  } finally {
    saving.value = false
  }
}

const saveDataSettings = async () => {
  saving.value = true
  try {
    await new Promise(resolve => setTimeout(resolve, 500))
    showSnackbar(t('admin.settings.dataSettingsSaved'))
  } catch (error) {
    showSnackbar(t('admin.settings.failedToSave'), 'error')
  } finally {
    saving.value = false
  }
}

const exportData = () => {
  showSnackbar(t('admin.settings.exportStarted'), 'info')
}

onMounted(async () => {
  await loadClients()
  await loadThresholds()
})
</script>
