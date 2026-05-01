<template>
  <div class="workflow-step-downtime">
    <!-- Summary -->
    <v-row class="mb-4">
      <v-col cols="6" md="3">
        <v-card variant="outlined" class="text-center pa-3">
          <div class="text-h4 text-primary">{{ totalIncidents }}</div>
          <div class="text-caption text-grey">{{ $t('workflow.totalIncidents') }}</div>
        </v-card>
      </v-col>
      <v-col cols="6" md="3">
        <v-card variant="outlined" class="text-center pa-3">
          <div class="text-h4 text-success">{{ resolvedCount }}</div>
          <div class="text-caption text-grey">{{ $t('workflow.resolved') }}</div>
        </v-card>
      </v-col>
      <v-col cols="6" md="3">
        <v-card variant="outlined" class="text-center pa-3">
          <div class="text-h4" :class="openCount > 0 ? 'text-error' : 'text-grey'">
            {{ openCount }}
          </div>
          <div class="text-caption text-grey">{{ $t('workflow.needsAttention') }}</div>
        </v-card>
      </v-col>
      <v-col cols="6" md="3">
        <v-card variant="outlined" class="text-center pa-3">
          <div class="text-h4 text-warning">{{ totalMinutes }}</div>
          <div class="text-caption text-grey">{{ $t('workflow.totalMinutes') }}</div>
        </v-card>
      </v-col>
    </v-row>

    <!-- Open Incidents (read-only — link out to grid for entry) -->
    <v-card
      v-if="openIncidents.length > 0"
      variant="outlined"
      class="mb-4 border-error"
    >
      <v-card-title class="d-flex align-center bg-red-lighten-4 py-2">
        <v-icon class="mr-2" size="20" color="error">mdi-alert-circle</v-icon>
        {{ $t('workflow.openDowntimeIncidents') }}
        <v-chip size="small" color="error" class="ml-2">
          {{ $t('workflow.toResolve', { count: openIncidents.length }) }}
        </v-chip>
        <v-spacer />
        <v-btn
          size="small"
          color="primary"
          variant="elevated"
          :to="{ path: '/data-entry/downtime' }"
          target="_blank"
        >
          <v-icon start size="16">mdi-open-in-new</v-icon>
          {{ $t('workflow.openDowntimeGrid') }}
        </v-btn>
      </v-card-title>

      <v-card-text class="pa-0">
        <v-list density="compact">
          <v-list-item
            v-for="incident in openIncidents"
            :key="incident.downtime_entry_id"
            class="border-b"
          >
            <template v-slot:prepend>
              <v-avatar color="error" size="36">
                <v-icon color="white" size="18">mdi-clock-alert</v-icon>
              </v-avatar>
            </template>

            <v-list-item-title class="font-weight-medium">
              {{ incident.machine_id || incident.equipment_code || $t('workflow.unspecifiedMachine') }}
            </v-list-item-title>
            <v-list-item-subtitle>
              {{ formatReason(incident.downtime_reason) }} —
              {{ incident.downtime_duration_minutes || 0 }} min
            </v-list-item-subtitle>
          </v-list-item>
        </v-list>
      </v-card-text>
    </v-card>

    <!-- Resolved Incidents -->
    <v-card variant="outlined" class="mb-4">
      <v-card-title class="d-flex align-center bg-grey-lighten-4 py-2">
        <v-icon class="mr-2" size="20">mdi-clipboard-check</v-icon>
        {{ $t('workflow.resolvedIncidentsThisShift') }}
      </v-card-title>

      <v-card-text class="pa-0">
        <v-skeleton-loader v-if="loading" type="list-item-two-line@3" />
        <v-alert
          v-else-if="resolvedIncidents.length === 0"
          type="info"
          variant="tonal"
          class="ma-3"
        >
          {{ $t('workflow.noResolvedIncidents') }}
        </v-alert>
        <v-list v-else density="compact">
          <v-list-item
            v-for="incident in resolvedIncidents"
            :key="incident.downtime_entry_id"
          >
            <template v-slot:prepend>
              <v-avatar color="success" size="36">
                <v-icon color="white" size="18">mdi-check-circle</v-icon>
              </v-avatar>
            </template>

            <v-list-item-title>
              {{ incident.machine_id || incident.equipment_code || $t('workflow.unspecifiedMachine') }}
            </v-list-item-title>
            <v-list-item-subtitle>
              {{ formatReason(incident.downtime_reason) }} —
              {{ incident.downtime_duration_minutes || 0 }} min
            </v-list-item-subtitle>

            <template v-slot:append v-if="incident.corrective_action">
              <v-tooltip :text="incident.corrective_action" location="left">
                <template v-slot:activator="{ props }">
                  <v-icon v-bind="props" size="16" color="grey">mdi-information</v-icon>
                </template>
              </v-tooltip>
            </template>
          </v-list-item>
        </v-list>
      </v-card-text>
    </v-card>

    <!-- Downtime by Reason -->
    <v-card variant="outlined" class="mb-4">
      <v-card-title class="bg-grey-lighten-4 py-2">
        <v-icon class="mr-2" size="20">mdi-chart-pie</v-icon>
        {{ $t('workflow.downtimeByReason') }}
      </v-card-title>
      <v-card-text>
        <v-alert
          v-if="downtimeByReason.length === 0"
          type="info"
          variant="tonal"
          density="compact"
        >
          {{ $t('workflow.noDowntimeData') }}
        </v-alert>
        <div v-else>
          <div v-for="reason in downtimeByReason" :key="reason.code" class="mb-3">
            <div class="d-flex justify-space-between align-center mb-1">
              <span class="text-body-2">{{ formatReason(reason.code) }}</span>
              <span class="text-caption text-grey">
                {{ reason.minutes }} min ({{ reason.percentage }}%)
              </span>
            </div>
            <v-progress-linear
              :model-value="reason.percentage"
              :color="reason.color"
              height="8"
              rounded
            />
          </div>
        </div>
      </v-card-text>
    </v-card>

    <!-- Confirmation -->
    <v-checkbox
      v-model="confirmed"
      :disabled="openCount > 0"
      :label="$t('workflow.downtimeConfirmLabel')"
      color="primary"
      @update:model-value="handleConfirm"
    />

    <v-alert
      v-if="openCount > 0"
      type="error"
      variant="tonal"
      density="compact"
      class="mt-2"
    >
      {{ $t('workflow.downtimeMustResolve', { count: openCount }) }}
    </v-alert>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { format } from 'date-fns'
import { useI18n } from 'vue-i18n'
import api from '@/services/api'
import { useAuthStore } from '@/stores/authStore'
import { useKPIStore } from '@/stores/kpi'
import { useNotificationStore } from '@/stores/notificationStore'

const { t } = useI18n()
const emit = defineEmits(['complete', 'update'])

const authStore = useAuthStore()
const kpiStore = useKPIStore()
const notificationStore = useNotificationStore()

const loading = ref(true)
const confirmed = ref(false)
const incidents = ref([])

// "Open" = no corrective_action recorded yet (operator must add one in the Downtime grid).
const openIncidents = computed(() =>
  incidents.value.filter((i) => !(i.corrective_action || '').trim()),
)
const resolvedIncidents = computed(() =>
  incidents.value.filter((i) => (i.corrective_action || '').trim()),
)
const totalIncidents = computed(() => incidents.value.length)
const resolvedCount = computed(() => resolvedIncidents.value.length)
const openCount = computed(() => openIncidents.value.length)
const totalMinutes = computed(() =>
  incidents.value.reduce((sum, i) => sum + (i.downtime_duration_minutes || 0), 0),
)

const reasonColorMap = {
  EQUIPMENT_FAILURE: 'error',
  MATERIAL_SHORTAGE: 'warning',
  SETUP_CHANGEOVER: 'info',
  QUALITY_HOLD: 'pink',
  MAINTENANCE: 'primary',
  POWER_OUTAGE: 'error',
  OTHER: 'grey',
}

const formatReason = (code) => {
  if (!code) return t('workflow.unspecifiedReason')
  return code
    .split('_')
    .map((w) => w.charAt(0) + w.slice(1).toLowerCase())
    .join(' ')
}

const downtimeByReason = computed(() => {
  const buckets = new Map()
  incidents.value.forEach((i) => {
    const code = i.downtime_reason || 'OTHER'
    const minutes = i.downtime_duration_minutes || 0
    buckets.set(code, (buckets.get(code) || 0) + minutes)
  })
  return [...buckets.entries()]
    .map(([code, minutes]) => ({
      code,
      minutes,
      percentage:
        totalMinutes.value > 0 ? Math.round((minutes / totalMinutes.value) * 100) : 0,
      color: reasonColorMap[code] || 'grey',
    }))
    .sort((a, b) => b.minutes - a.minutes)
})

const emitUpdate = () => {
  emit('update', {
    incidents: incidents.value,
    openCount: openCount.value,
    totalMinutes: totalMinutes.value,
    isValid: confirmed.value && openCount.value === 0,
  })
}

const handleConfirm = (value) => {
  if (value && openCount.value === 0) {
    emit('complete', {
      incidents: incidents.value,
      totalIncidents: totalIncidents.value,
      totalMinutes: totalMinutes.value,
      byReason: downtimeByReason.value,
    })
  }
  emitUpdate()
}

const fetchData = async () => {
  loading.value = true
  try {
    const params = { shift_date: format(new Date(), 'yyyy-MM-dd') }
    const clientId = authStore.user?.client_id_assigned ?? kpiStore.selectedClient
    if (clientId) params.client_id = clientId
    const response = await api.get('/downtime', { params })
    incidents.value = (response.data || []).map((entry) => ({
      ...entry,
      shift_date:
        typeof entry.shift_date === 'string'
          ? entry.shift_date.slice(0, 10)
          : entry.shift_date,
    }))
    emitUpdate()
  } catch (error) {
    // eslint-disable-next-line no-console
    console.error('Failed to fetch downtime data:', error)
    notificationStore.show({
      type: 'error',
      message: t('workflow.errors.loadDowntime'),
    })
    incidents.value = []
    emitUpdate()
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.border-error {
  border-color: rgb(var(--v-theme-error)) !important;
}

.border-b {
  border-bottom: 1px solid rgba(0, 0, 0, 0.12);
}
</style>
