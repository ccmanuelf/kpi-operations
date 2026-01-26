<template>
  <div class="workflow-step-attendance">
    <!-- Attendance Summary -->
    <v-row class="mb-4">
      <v-col cols="4">
        <v-card variant="outlined" class="text-center pa-3">
          <div class="text-h4 text-primary">{{ expectedCount }}</div>
          <div class="text-caption text-grey">Expected</div>
        </v-card>
      </v-col>
      <v-col cols="4">
        <v-card variant="outlined" class="text-center pa-3">
          <div class="text-h4 text-success">{{ presentCount }}</div>
          <div class="text-caption text-grey">Present</div>
        </v-card>
      </v-col>
      <v-col cols="4">
        <v-card variant="outlined" class="text-center pa-3">
          <div class="text-h4" :class="absentCount > 0 ? 'text-error' : 'text-grey'">
            {{ absentCount }}
          </div>
          <div class="text-caption text-grey">Absent</div>
        </v-card>
      </v-col>
    </v-row>

    <!-- Employee List -->
    <v-card variant="outlined" class="mb-4">
      <v-card-title class="d-flex align-center bg-grey-lighten-4 py-2">
        <v-icon class="mr-2" size="20">mdi-account-group</v-icon>
        Employee Attendance
        <v-spacer />
        <v-text-field
          v-model="searchQuery"
          density="compact"
          variant="outlined"
          placeholder="Search..."
          prepend-inner-icon="mdi-magnify"
          hide-details
          single-line
          style="max-width: 200px"
        />
      </v-card-title>

      <v-card-text class="pa-0">
        <v-skeleton-loader v-if="loading" type="list-item-avatar-two-line@5" />
        <v-list v-else density="compact" class="employee-list">
          <v-list-item
            v-for="employee in filteredEmployees"
            :key="employee.id"
            :class="{ 'bg-red-lighten-5': !employee.present }"
          >
            <template v-slot:prepend>
              <v-avatar
                :color="employee.present ? 'success' : 'error'"
                size="36"
              >
                <v-icon color="white" size="20">
                  {{ employee.present ? 'mdi-check' : 'mdi-close' }}
                </v-icon>
              </v-avatar>
            </template>

            <v-list-item-title>{{ employee.name }}</v-list-item-title>
            <v-list-item-subtitle>
              {{ employee.role }} - {{ employee.station || 'Unassigned' }}
            </v-list-item-subtitle>

            <template v-slot:append>
              <v-btn-toggle
                v-model="employee.present"
                mandatory
                density="compact"
                @update:model-value="updateAttendance(employee)"
              >
                <v-btn :value="true" color="success" size="small" variant="outlined">
                  <v-icon size="16">mdi-check</v-icon>
                </v-btn>
                <v-btn :value="false" color="error" size="small" variant="outlined">
                  <v-icon size="16">mdi-close</v-icon>
                </v-btn>
              </v-btn-toggle>
            </template>
          </v-list-item>
        </v-list>
      </v-card-text>
    </v-card>

    <!-- Station Assignments -->
    <v-card variant="outlined" class="mb-4">
      <v-card-title class="d-flex align-center bg-grey-lighten-4 py-2">
        <v-icon class="mr-2" size="20">mdi-account-hard-hat</v-icon>
        Station Assignments
        <v-spacer />
        <v-btn
          variant="text"
          size="small"
          color="primary"
          @click="autoAssign"
          :disabled="loading"
        >
          <v-icon start size="16">mdi-auto-fix</v-icon>
          Auto-Assign
        </v-btn>
      </v-card-title>

      <v-card-text>
        <v-row>
          <v-col
            v-for="station in stations"
            :key="station.id"
            cols="12"
            sm="6"
            md="4"
          >
            <v-card
              variant="outlined"
              :class="{ 'border-success': station.assignedEmployee }"
            >
              <v-card-text class="pa-3">
                <div class="d-flex align-center mb-2">
                  <v-icon size="18" class="mr-2" color="grey">mdi-tools</v-icon>
                  <span class="text-body-2 font-weight-medium">{{ station.name }}</span>
                </div>
                <v-select
                  v-model="station.assignedEmployee"
                  :items="availableEmployees"
                  item-title="name"
                  item-value="id"
                  density="compact"
                  variant="outlined"
                  placeholder="Select operator"
                  hide-details
                  clearable
                  @update:model-value="updateAssignment(station)"
                />
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <!-- Coverage Alert -->
    <v-alert
      v-if="coverageIssue"
      type="warning"
      variant="tonal"
      class="mb-4"
    >
      <v-alert-title>Coverage Issue</v-alert-title>
      {{ coverageMessage }}
      <template v-slot:append>
        <v-btn variant="text" size="small" @click="requestFloatingPool">
          Request Coverage
        </v-btn>
      </template>
    </v-alert>

    <!-- Confirmation -->
    <v-checkbox
      v-model="confirmed"
      :disabled="!isValid"
      label="I confirm the attendance and station assignments are correct"
      color="primary"
      @update:model-value="handleConfirm"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import api from '@/services/api'

const emit = defineEmits(['complete', 'update'])

// State
const loading = ref(true)
const searchQuery = ref('')
const confirmed = ref(false)
const employees = ref([])
const stations = ref([])

// Computed
const expectedCount = computed(() => employees.value.length)
const presentCount = computed(() => employees.value.filter(e => e.present).length)
const absentCount = computed(() => employees.value.filter(e => !e.present).length)

const filteredEmployees = computed(() => {
  if (!searchQuery.value) return employees.value
  const query = searchQuery.value.toLowerCase()
  return employees.value.filter(e =>
    e.name.toLowerCase().includes(query) ||
    e.role.toLowerCase().includes(query)
  )
})

const availableEmployees = computed(() => {
  return employees.value.filter(e => e.present)
})

const coverageIssue = computed(() => {
  const required = stations.value.length
  const available = presentCount.value
  return available < required
})

const coverageMessage = computed(() => {
  const shortfall = stations.value.length - presentCount.value
  return `${shortfall} additional operator(s) needed for full coverage.`
})

const isValid = computed(() => {
  // At least 80% attendance required
  const attendancePercent = (presentCount.value / expectedCount.value) * 100
  return attendancePercent >= 80
})

// Methods
const updateAttendance = (employee) => {
  emitUpdate()
}

const updateAssignment = (station) => {
  emitUpdate()
}

const autoAssign = () => {
  const available = [...availableEmployees.value]
  stations.value.forEach(station => {
    if (!station.assignedEmployee && available.length > 0) {
      const employee = available.shift()
      station.assignedEmployee = employee.id
    }
  })
  emitUpdate()
}

const requestFloatingPool = () => {
  // This would trigger a notification/request in a real implementation
  console.log('Requesting floating pool coverage')
}

const handleConfirm = (value) => {
  if (value && isValid.value) {
    emit('complete', {
      employees: employees.value,
      stations: stations.value,
      presentCount: presentCount.value,
      absentCount: absentCount.value
    })
  }
  emitUpdate()
}

const emitUpdate = () => {
  emit('update', {
    employees: employees.value,
    stations: stations.value,
    isValid: isValid.value && confirmed.value
  })
}

const fetchData = async () => {
  loading.value = true
  try {
    const [employeesRes, stationsRes] = await Promise.all([
      api.get('/employees/shift-roster'),
      api.get('/stations')
    ])
    employees.value = employeesRes.data
    stations.value = stationsRes.data
  } catch (error) {
    console.error('Failed to fetch attendance data:', error)
    // Mock data for demonstration
    employees.value = [
      { id: 1, name: 'John Smith', role: 'Operator', present: true, station: 'Line 1' },
      { id: 2, name: 'Maria Garcia', role: 'Operator', present: true, station: 'Line 2' },
      { id: 3, name: 'James Wilson', role: 'Operator', present: true, station: null },
      { id: 4, name: 'Sarah Johnson', role: 'Quality Inspector', present: true, station: null },
      { id: 5, name: 'Michael Brown', role: 'Operator', present: false, station: null },
      { id: 6, name: 'Emily Davis', role: 'Operator', present: true, station: 'Line 3' },
      { id: 7, name: 'David Martinez', role: 'Technician', present: true, station: null },
      { id: 8, name: 'Lisa Anderson', role: 'Operator', present: true, station: null }
    ]
    stations.value = [
      { id: 1, name: 'Line 1', assignedEmployee: 1 },
      { id: 2, name: 'Line 2', assignedEmployee: 2 },
      { id: 3, name: 'Line 3', assignedEmployee: 6 },
      { id: 4, name: 'Line 4', assignedEmployee: null },
      { id: 5, name: 'Quality Station', assignedEmployee: 4 }
    ]
  } finally {
    loading.value = false
  }
}

// Watch for validity changes
watch(isValid, (newValue) => {
  emitUpdate()
})

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.employee-list {
  max-height: 300px;
  overflow-y: auto;
}

.border-success {
  border-color: rgb(var(--v-theme-success)) !important;
}
</style>
