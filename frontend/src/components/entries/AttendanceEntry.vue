<template>
  <v-skeleton-loader
    v-if="initialLoading"
    type="card, article, actions"
    class="mb-4"
  />
  <v-card v-else>
    <v-card-title class="d-flex justify-space-between align-center">
      <div>
        <v-icon class="mr-2">mdi-account-clock</v-icon>
        {{ $t('attendance.entry') }}
      </div>
      <CSVUploadDialogAttendance @imported="onImported" />
    </v-card-title>
    <v-card-text>
      <v-form ref="form" v-model="valid">
        <v-row>
          <v-col cols="12" md="6">
            <v-text-field
              v-model="formData.employee_id"
              :label="`${$t('attendance.employee')} ID *`"
              :rules="[rules.required]"
              variant="outlined"
              density="comfortable"
            />
          </v-col>
          <v-col cols="12" md="6">
            <v-text-field
              v-model="formData.date"
              type="date"
              :label="`${$t('common.date')} *`"
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
              :label="`${$t('production.shift')} *`"
              :rules="[rules.required]"
              variant="outlined"
              density="comfortable"
            />
          </v-col>
          <v-col cols="12" md="6">
            <v-select
              v-model="formData.status"
              :items="statuses"
              item-title="title"
              item-value="value"
              :label="`${$t('common.status')} *`"
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
              item-title="title"
              item-value="value"
              :label="`${$t('downtime.reason')} *`"
              :rules="[rules.required]"
              variant="outlined"
              density="comfortable"
            />
          </v-col>
          <v-col cols="12" md="6">
            <v-checkbox
              v-model="formData.is_excused"
              :label="$t('attendance.excused')"
              density="comfortable"
            />
          </v-col>
        </v-row>

        <v-row v-if="formData.status === 'Late'">
          <v-col cols="12" md="6">
            <v-text-field
              v-model.number="formData.late_minutes"
              type="number"
              :label="`${$t('downtime.minutes')} ${$t('attendance.late')}`"
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
              :label="$t('common.time')"
              variant="outlined"
              density="comfortable"
            />
          </v-col>
          <v-col cols="12" md="6">
            <v-text-field
              v-model="formData.clock_out"
              type="time"
              :label="$t('common.time')"
              variant="outlined"
              density="comfortable"
            />
          </v-col>
        </v-row>

        <v-row>
          <v-col cols="12">
            <v-textarea
              v-model="formData.notes"
              :label="$t('production.notes')"
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
        {{ $t('common.submit') }} {{ $t('attendance.title') }}
      </v-btn>
    </v-card-actions>

    <!-- Read-Back Confirmation Dialog -->
    <ReadBackConfirmation
      v-model="showConfirmDialog"
      :title="$t('readBack.confirmEntry')"
      :subtitle="$t('readBack.verifyBeforeSaving')"
      :data="formData"
      :field-config="confirmationFieldConfig"
      :loading="loading"
      @confirm="onConfirmSave"
      @cancel="onCancelSave"
    />

    <!-- Snackbar -->
    <v-snackbar
      v-model="snackbar.show"
      :color="snackbar.color"
      :timeout="3000"
    >
      {{ snackbar.text }}
    </v-snackbar>
  </v-card>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/services/api'
import CSVUploadDialogAttendance from '@/components/CSVUploadDialogAttendance.vue'
import ReadBackConfirmation from '@/components/dialogs/ReadBackConfirmation.vue'

const { t } = useI18n()

const emit = defineEmits(['submitted'])

const form = ref(null)
const valid = ref(false)
const loading = ref(false)
const initialLoading = ref(true)
const shifts = ref([])
const showConfirmDialog = ref(false)
const snackbar = ref({ show: false, text: '', color: 'info' })

const statuses = computed(() => [
  { title: t('attendance.statuses.present'), value: 'Present' },
  { title: t('attendance.statuses.absent'), value: 'Absent' },
  { title: t('attendance.statuses.late'), value: 'Late' },
  { title: t('attendance.statuses.halfDay'), value: 'Half Day' },
  { title: t('attendance.statuses.leave'), value: 'Leave' }
])
const absenceReasons = computed(() => [
  { title: t('attendance.reasons.sickLeave'), value: 'Sick Leave' },
  { title: t('attendance.reasons.personalLeave'), value: 'Personal Leave' },
  { title: t('attendance.reasons.familyEmergency'), value: 'Family Emergency' },
  { title: t('attendance.reasons.medicalAppointment'), value: 'Medical Appointment' },
  { title: t('attendance.reasons.noShow'), value: 'No Show' },
  { title: t('attendance.reasons.unauthorized'), value: 'Unauthorized' },
  { title: t('attendance.reasons.other'), value: 'Other' }
])

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
  required: value => !!value || t('validation.required')
}

// Field configuration for confirmation dialog
const confirmationFieldConfig = computed(() => {
  const shiftName = shifts.value.find(s => s.id === formData.value.shift_id)?.name || 'N/A'

  return [
    { key: 'employee_id', label: t('attendance.employee') + ' ID', type: 'text' },
    { key: 'date', label: t('common.date'), type: 'date' },
    { key: 'shift_id', label: t('production.shift'), type: 'text', displayValue: shiftName },
    { key: 'status', label: t('common.status'), type: 'text' },
    { key: 'absence_reason', label: t('downtime.reason'), type: 'text' },
    { key: 'is_excused', label: t('attendance.excused'), type: 'boolean' },
    { key: 'late_minutes', label: t('downtime.minutes') + ' ' + t('attendance.late'), type: 'number' },
    { key: 'clock_in', label: t('common.time') + ' In', type: 'text' },
    { key: 'clock_out', label: t('common.time') + ' Out', type: 'text' },
    { key: 'notes', label: t('production.notes'), type: 'text' }
  ]
})

const onImported = () => {
  emit('submitted')
}

const submitEntry = async () => {
  const { valid: isValid } = await form.value.validate()
  if (!isValid) return

  // Show read-back confirmation dialog
  showConfirmDialog.value = true
}

const onConfirmSave = async () => {
  showConfirmDialog.value = false
  loading.value = true

  try {
    await api.createAttendanceEntry(formData.value)

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
    snackbar.value = {
      show: true,
      text: t('attendance.errors.createEntry') + ': ' + (error.response?.data?.detail || error.message),
      color: 'error'
    }
  } finally {
    loading.value = false
  }
}

const onCancelSave = () => {
  showConfirmDialog.value = false
}

const loadShifts = async () => {
  try {
    const response = await api.getShifts()
    shifts.value = response.data
  } catch (error) {
    console.error('Error loading shifts:', error)
  } finally {
    initialLoading.value = false
  }
}

onMounted(() => {
  loadShifts()
  formData.value.date = new Date().toISOString().split('T')[0]
})
</script>
