<template>
  <v-card>
    <v-card-title class="d-flex justify-space-between align-center">
      <div>
        <v-icon class="mr-2">mdi-account-clock</v-icon>
        Attendance Entry
      </div>
      <CSVUploadDialogAttendance @imported="onImported" />
    </v-card-title>
    <v-card-text>
      <v-form ref="form" v-model="valid">
        <v-row>
          <v-col cols="12" md="6">
            <v-text-field
              v-model="formData.employee_id"
              label="Employee ID *"
              :rules="[rules.required]"
              variant="outlined"
              density="comfortable"
            />
          </v-col>
          <v-col cols="12" md="6">
            <v-text-field
              v-model="formData.date"
              type="date"
              label="Date *"
              :rules="[rules.required]"
              variant="outlined"
              density="comfortable"
            />
          </v-col>
        </v-row>

        <v-row>
          <v-col cols="12" md="6">
            <v-select
              v-model="formData.shift_id"
              :items="shifts"
              item-title="name"
              item-value="id"
              label="Shift *"
              :rules="[rules.required]"
              variant="outlined"
              density="comfortable"
            />
          </v-col>
          <v-col cols="12" md="6">
            <v-select
              v-model="formData.status"
              :items="statuses"
              label="Status *"
              :rules="[rules.required]"
              variant="outlined"
              density="comfortable"
            />
          </v-col>
        </v-row>

        <v-row v-if="formData.status === 'Absent'">
          <v-col cols="12" md="6">
            <v-select
              v-model="formData.absence_reason"
              :items="absenceReasons"
              label="Absence Reason *"
              :rules="[rules.required]"
              variant="outlined"
              density="comfortable"
            />
          </v-col>
          <v-col cols="12" md="6">
            <v-checkbox
              v-model="formData.is_excused"
              label="Excused Absence"
              density="comfortable"
            />
          </v-col>
        </v-row>

        <v-row v-if="formData.status === 'Late'">
          <v-col cols="12" md="6">
            <v-text-field
              v-model.number="formData.late_minutes"
              type="number"
              label="Minutes Late"
              variant="outlined"
              density="comfortable"
            />
          </v-col>
        </v-row>

        <v-row>
          <v-col cols="12" md="6">
            <v-text-field
              v-model="formData.clock_in"
              type="time"
              label="Clock In Time"
              variant="outlined"
              density="comfortable"
            />
          </v-col>
          <v-col cols="12" md="6">
            <v-text-field
              v-model="formData.clock_out"
              type="time"
              label="Clock Out Time"
              variant="outlined"
              density="comfortable"
            />
          </v-col>
        </v-row>

        <v-row>
          <v-col cols="12">
            <v-textarea
              v-model="formData.notes"
              label="Notes"
              rows="3"
              variant="outlined"
              density="comfortable"
            />
          </v-col>
        </v-row>
      </v-form>
    </v-card-text>
    <v-card-actions>
      <v-spacer />
      <v-btn
        color="primary"
        :disabled="!valid"
        :loading="loading"
        @click="submitEntry"
      >
        Submit Attendance
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '@/services/api'
import CSVUploadDialogAttendance from '@/components/CSVUploadDialogAttendance.vue'

const emit = defineEmits(['submitted'])

const form = ref(null)
const valid = ref(false)
const loading = ref(false)
const shifts = ref([])

const statuses = ['Present', 'Absent', 'Late', 'Half Day', 'Leave']
const absenceReasons = [
  'Sick Leave',
  'Personal Leave',
  'Family Emergency',
  'Medical Appointment',
  'No Show',
  'Unauthorized',
  'Other'
]

const formData = ref({
  employee_id: '',
  date: '',
  shift_id: null,
  status: 'Present',
  absence_reason: '',
  is_excused: false,
  late_minutes: 0,
  clock_in: '',
  clock_out: '',
  notes: ''
})

const rules = {
  required: value => !!value || 'Field is required'
}

const onImported = () => {
  emit('submitted')
}

const submitEntry = async () => {
  const { valid: isValid } = await form.value.validate()
  if (!isValid) return

  loading.value = true
  try {
    await api.createAttendanceEntry(formData.value)

    alert('Attendance entry created successfully!')

    formData.value = {
      employee_id: '',
      date: '',
      shift_id: null,
      status: 'Present',
      absence_reason: '',
      is_excused: false,
      late_minutes: 0,
      clock_in: '',
      clock_out: '',
      notes: ''
    }
    form.value.reset()

    emit('submitted')
  } catch (error) {
    alert('Error creating attendance entry: ' + (error.response?.data?.detail || error.message))
  } finally {
    loading.value = false
  }
}

const loadShifts = async () => {
  try {
    const response = await api.getShifts()
    shifts.value = response.data
  } catch (error) {
    console.error('Error loading shifts:', error)
  }
}

onMounted(() => {
  loadShifts()
  formData.value.date = new Date().toISOString().split('T')[0]
})
</script>
