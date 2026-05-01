<template>
  <div class="workflow-step-attendance">
    <!-- Attendance Summary -->
    <v-row class="mb-4">
      <v-col cols="4">
        <v-card variant="outlined" class="text-center pa-3">
          <div class="text-h4 text-primary">{{ expectedCount }}</div>
          <div class="text-caption text-grey">{{ $t('workflow.expected') }}</div>
        </v-card>
      </v-col>
      <v-col cols="4">
        <v-card variant="outlined" class="text-center pa-3">
          <div class="text-h4 text-success">{{ presentCount }}</div>
          <div class="text-caption text-grey">{{ $t('workflow.present') }}</div>
        </v-card>
      </v-col>
      <v-col cols="4">
        <v-card variant="outlined" class="text-center pa-3">
          <div class="text-h4" :class="absentCount > 0 ? 'text-error' : 'text-grey'">
            {{ absentCount }}
          </div>
          <div class="text-caption text-grey">{{ $t('workflow.absent') }}</div>
        </v-card>
      </v-col>
    </v-row>

    <!-- Employee List (read-only roster from canonical /api/employees) -->
    <v-card variant="outlined" class="mb-4">
      <v-card-title class="d-flex align-center bg-grey-lighten-4 py-2">
        <v-icon class="mr-2" size="20">mdi-account-group</v-icon>
        {{ $t('workflow.employeeAttendance') }}
        <v-spacer />
        <v-btn
          size="small"
          color="primary"
          variant="elevated"
          :to="{ path: '/data-entry/attendance' }"
          target="_blank"
          class="mr-2"
        >
          <v-icon start size="16">mdi-open-in-new</v-icon>
          {{ $t('workflow.openAttendanceGrid') }}
        </v-btn>
        <v-text-field
          v-model="searchQuery"
          density="compact"
          variant="outlined"
          :placeholder="$t('common.search')"
          prepend-inner-icon="mdi-magnify"
          hide-details
          single-line
          style="max-width: 200px"
        />
      </v-card-title>

      <v-card-text class="pa-0">
        <v-skeleton-loader v-if="loading" type="list-item-avatar-two-line@5" />
        <v-alert
          v-else-if="employees.length === 0"
          type="info"
          variant="tonal"
          class="ma-3"
        >
          {{ $t('workflow.noEmployeesFound') }}
        </v-alert>
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
              {{ employee.role || $t('workflow.unspecifiedRole') }}
            </v-list-item-subtitle>

            <template v-slot:append>
              <v-btn-toggle
                v-model="employee.present"
                mandatory
                density="compact"
                @update:model-value="emitUpdate"
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

    <!-- Coverage Alert -->
    <v-alert
      v-if="!hasCoverage"
      type="warning"
      variant="tonal"
      class="mb-4"
    >
      <v-alert-title>{{ $t('workflow.coverageIssue') }}</v-alert-title>
      {{ $t('workflow.coverageMessage', { count: minRequired - presentCount }) }}
    </v-alert>

    <!-- Persistence note -->
    <v-alert
      type="info"
      variant="tonal"
      density="compact"
      class="mb-4"
    >
      {{ $t('workflow.attendancePersistenceNote') }}
    </v-alert>

    <!-- Confirmation -->
    <v-checkbox
      v-model="confirmed"
      :disabled="!canConfirm"
      :label="$t('workflow.attendanceConfirmLabel')"
      color="primary"
      @update:model-value="handleConfirm"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
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
const searchQuery = ref('')
const confirmed = ref(false)
const employees = ref([])

const expectedCount = computed(() => employees.value.length)
const presentCount = computed(() => employees.value.filter((e) => e.present).length)
const absentCount = computed(() => employees.value.filter((e) => !e.present).length)

const filteredEmployees = computed(() => {
  if (!searchQuery.value) return employees.value
  const query = searchQuery.value.toLowerCase()
  return employees.value.filter(
    (e) =>
      (e.name || '').toLowerCase().includes(query) ||
      (e.role || '').toLowerCase().includes(query),
  )
})

// Coverage threshold: 80% of expected employees must be present.
const minRequired = computed(() => Math.ceil(expectedCount.value * 0.8))
const hasCoverage = computed(() => presentCount.value >= minRequired.value)
const canConfirm = computed(() => expectedCount.value > 0 && hasCoverage.value)

const isValid = computed(() => canConfirm.value && confirmed.value)

const emitUpdate = () => {
  emit('update', {
    employees: employees.value,
    presentCount: presentCount.value,
    absentCount: absentCount.value,
    isValid: isValid.value,
  })
}

const handleConfirm = (value) => {
  if (value && canConfirm.value) {
    emit('complete', {
      employees: employees.value,
      presentCount: presentCount.value,
      absentCount: absentCount.value,
    })
  }
  emitUpdate()
}

const fetchData = async () => {
  loading.value = true
  try {
    const params = { active: true }
    const clientId = authStore.user?.client_id_assigned ?? kpiStore.selectedClient
    if (clientId) params.client_id = clientId
    const response = await api.get('/employees', { params })
    employees.value = (response.data || []).map((e) => ({
      id: e.employee_id ?? e.id,
      name:
        e.employee_name ??
        e.name ??
        [e.first_name, e.last_name].filter(Boolean).join(' '),
      role: e.role ?? e.position ?? '',
      // Default everyone to "present" until the operator marks otherwise.
      // Persistence happens later via the standalone Attendance Entry grid.
      present: true,
    }))
    emitUpdate()
  } catch (error) {
    // eslint-disable-next-line no-console
    console.error('Failed to fetch employee roster:', error)
    notificationStore.show({
      type: 'error',
      message: t('workflow.errors.loadRoster'),
    })
    employees.value = []
    emitUpdate()
  } finally {
    loading.value = false
  }
}

watch([presentCount, expectedCount], () => emitUpdate())

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.employee-list {
  max-height: 300px;
  overflow-y: auto;
}
</style>
