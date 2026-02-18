<template>
  <div class="workflow-step-equipment">
    <!-- Equipment Status Overview -->
    <v-row class="mb-4">
      <v-col cols="6" md="3">
        <v-card variant="outlined" class="text-center pa-3">
          <div class="text-h4 text-success">{{ operationalCount }}</div>
          <div class="text-caption text-grey">{{ $t('workflow.operational') }}</div>
        </v-card>
      </v-col>
      <v-col cols="6" md="3">
        <v-card variant="outlined" class="text-center pa-3">
          <div class="text-h4 text-warning">{{ warningCount }}</div>
          <div class="text-caption text-grey">{{ $t('workflow.warnings') }}</div>
        </v-card>
      </v-col>
      <v-col cols="6" md="3">
        <v-card variant="outlined" class="text-center pa-3">
          <div class="text-h4 text-error">{{ downCount }}</div>
          <div class="text-caption text-grey">{{ $t('workflow.down') }}</div>
        </v-card>
      </v-col>
      <v-col cols="6" md="3">
        <v-card variant="outlined" class="text-center pa-3">
          <div class="text-h4 text-info">{{ pmDueCount }}</div>
          <div class="text-caption text-grey">{{ $t('workflow.pmDue') }}</div>
        </v-card>
      </v-col>
    </v-row>

    <!-- Equipment List -->
    <v-card variant="outlined" class="mb-4">
      <v-card-title class="d-flex align-center bg-grey-lighten-4 py-2">
        <v-icon class="mr-2" size="20">mdi-cog</v-icon>
        {{ $t('workflow.equipmentStatus') }}
        <v-spacer />
        <v-btn-toggle
          v-model="statusFilter"
          mandatory
          density="compact"
          variant="outlined"
        >
          <v-btn value="all" size="small">{{ $t('common.all') }}</v-btn>
          <v-btn value="issues" size="small" color="warning">{{ $t('workflow.issues') }}</v-btn>
        </v-btn-toggle>
      </v-card-title>

      <v-card-text class="pa-0">
        <v-skeleton-loader v-if="loading" type="list-item-avatar-two-line@4" />
        <v-list v-else density="compact" class="equipment-list">
          <v-list-item
            v-for="equipment in filteredEquipment"
            :key="equipment.id"
            :class="getEquipmentClass(equipment.status)"
          >
            <template v-slot:prepend>
              <v-avatar :color="getStatusColor(equipment.status)" size="40">
                <v-icon color="white" size="20">{{ getStatusIcon(equipment.status) }}</v-icon>
              </v-avatar>
            </template>

            <v-list-item-title class="d-flex align-center">
              {{ equipment.name }}
              <v-chip
                v-if="equipment.pmDue"
                size="x-small"
                color="info"
                class="ml-2"
                variant="flat"
              >
                {{ $t('workflow.pmDue') }}
              </v-chip>
            </v-list-item-title>
            <v-list-item-subtitle>
              {{ equipment.location }} - {{ $t('workflow.lastCheck') }}: {{ formatTime(equipment.lastCheck) }}
            </v-list-item-subtitle>

            <template v-slot:append>
              <div class="text-right">
                <v-chip
                  :color="getStatusColor(equipment.status)"
                  size="small"
                  variant="tonal"
                >
                  {{ equipment.status }}
                </v-chip>
                <div v-if="equipment.notes" class="text-caption text-grey mt-1">
                  {{ equipment.notes }}
                </div>
              </div>
            </template>
          </v-list-item>
        </v-list>
      </v-card-text>
    </v-card>

    <!-- Maintenance Alerts -->
    <v-card
      v-if="maintenanceAlerts.length > 0"
      variant="outlined"
      class="mb-4"
    >
      <v-card-title class="d-flex align-center bg-warning-lighten-4 py-2">
        <v-icon class="mr-2" size="20" color="warning">mdi-alert</v-icon>
        {{ $t('workflow.maintenanceAlerts') }}
      </v-card-title>
      <v-card-text class="pa-0">
        <v-list density="compact">
          <v-list-item
            v-for="alert in maintenanceAlerts"
            :key="alert.id"
          >
            <template v-slot:prepend>
              <v-icon :color="getAlertColor(alert.severity)">
                {{ getAlertIcon(alert.severity) }}
              </v-icon>
            </template>
            <v-list-item-title>{{ alert.title }}</v-list-item-title>
            <v-list-item-subtitle>{{ alert.equipment }} - {{ alert.description }}</v-list-item-subtitle>
            <template v-slot:append>
              <v-btn
                size="small"
                variant="text"
                color="primary"
                @click="acknowledgeAlert(alert)"
              >
                {{ $t('workflow.acknowledge') }}
              </v-btn>
            </template>
          </v-list-item>
        </v-list>
      </v-card-text>
    </v-card>

    <!-- Equipment Check -->
    <v-alert
      v-if="downCount > 0"
      type="error"
      variant="tonal"
      class="mb-4"
    >
      <v-alert-title>{{ $t('workflow.equipmentDown') }}</v-alert-title>
      {{ $t('workflow.equipmentDownAlert', { count: downCount }) }}
    </v-alert>

    <!-- Confirmation -->
    <v-checkbox
      v-model="confirmed"
      :label="$t('workflow.equipmentConfirmLabel')"
      color="primary"
      @update:model-value="handleConfirm"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '@/services/api'

const emit = defineEmits(['complete', 'update'])

// State
const loading = ref(true)
const confirmed = ref(false)
const statusFilter = ref('all')
const equipment = ref([])
const maintenanceAlerts = ref([])

// Computed
const operationalCount = computed(() => equipment.value.filter(e => e.status === 'Operational').length)
const warningCount = computed(() => equipment.value.filter(e => e.status === 'Warning').length)
const downCount = computed(() => equipment.value.filter(e => e.status === 'Down').length)
const pmDueCount = computed(() => equipment.value.filter(e => e.pmDue).length)

const filteredEquipment = computed(() => {
  if (statusFilter.value === 'all') return equipment.value
  return equipment.value.filter(e => e.status !== 'Operational' || e.pmDue)
})

// Methods
const getStatusColor = (status) => {
  const colors = {
    Operational: 'success',
    Warning: 'warning',
    Down: 'error',
    Maintenance: 'info'
  }
  return colors[status] || 'grey'
}

const getStatusIcon = (status) => {
  const icons = {
    Operational: 'mdi-check-circle',
    Warning: 'mdi-alert-circle',
    Down: 'mdi-close-circle',
    Maintenance: 'mdi-wrench'
  }
  return icons[status] || 'mdi-help-circle'
}

const getEquipmentClass = (status) => {
  if (status === 'Down') return 'bg-red-lighten-5'
  if (status === 'Warning') return 'bg-orange-lighten-5'
  return ''
}

const getAlertColor = (severity) => {
  const colors = {
    critical: 'error',
    high: 'warning',
    medium: 'info',
    low: 'grey'
  }
  return colors[severity] || 'grey'
}

const getAlertIcon = (severity) => {
  if (severity === 'critical') return 'mdi-alert-octagon'
  if (severity === 'high') return 'mdi-alert'
  return 'mdi-information'
}

const formatTime = (timeString) => {
  if (!timeString) return 'Never'
  const date = new Date(timeString)
  const now = new Date()
  const diff = now - date
  const hours = Math.floor(diff / (1000 * 60 * 60))

  if (hours < 1) return 'Just now'
  if (hours < 24) return `${hours}h ago`
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

const acknowledgeAlert = (alert) => {
  const index = maintenanceAlerts.value.findIndex(a => a.id === alert.id)
  if (index !== -1) {
    maintenanceAlerts.value.splice(index, 1)
  }
}

const handleConfirm = (value) => {
  if (value) {
    emit('complete', {
      equipment: equipment.value,
      operationalCount: operationalCount.value,
      issuesCount: warningCount.value + downCount.value,
      acknowledgedAlerts: true
    })
  }
  emit('update', { isValid: value })
}

const fetchData = async () => {
  loading.value = true
  try {
    const [equipmentRes, alertsRes] = await Promise.all([
      api.get('/equipment/status'),
      api.get('/maintenance/alerts')
    ])
    equipment.value = equipmentRes.data
    maintenanceAlerts.value = alertsRes.data
  } catch (error) {
    console.error('Failed to fetch equipment data:', error)
    // Mock data for demonstration
    equipment.value = [
      { id: 1, name: 'CNC Machine #1', location: 'Line 1', status: 'Operational', pmDue: false, lastCheck: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(), notes: null },
      { id: 2, name: 'CNC Machine #2', location: 'Line 1', status: 'Warning', pmDue: true, lastCheck: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(), notes: 'Vibration sensor alert' },
      { id: 3, name: 'Assembly Station A', location: 'Line 2', status: 'Operational', pmDue: false, lastCheck: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString(), notes: null },
      { id: 4, name: 'Press #1', location: 'Line 2', status: 'Operational', pmDue: false, lastCheck: new Date(Date.now() - 1 * 60 * 60 * 1000).toISOString(), notes: null },
      { id: 5, name: 'Conveyor System', location: 'Main Floor', status: 'Operational', pmDue: true, lastCheck: new Date(Date.now() - 48 * 60 * 60 * 1000).toISOString(), notes: 'Belt replacement due' },
      { id: 6, name: 'Robot Arm #1', location: 'Line 3', status: 'Down', pmDue: false, lastCheck: new Date(Date.now() - 12 * 60 * 60 * 1000).toISOString(), notes: 'Motor replacement in progress' }
    ]
    maintenanceAlerts.value = [
      { id: 1, title: 'Preventive Maintenance Due', equipment: 'CNC Machine #2', severity: 'high', description: 'Scheduled PM overdue by 2 days' },
      { id: 2, title: 'Sensor Alert', equipment: 'Conveyor System', severity: 'medium', description: 'Belt tension below optimal range' }
    ]
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.equipment-list {
  max-height: 350px;
  overflow-y: auto;
}
</style>
