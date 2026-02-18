<template>
  <div class="workflow-step-start-shift">
    <!-- Shift Configuration -->
    <v-card variant="outlined" class="mb-4">
      <v-card-title class="bg-grey-lighten-4 py-2">
        <v-icon class="mr-2" size="20">mdi-calendar-clock</v-icon>
        {{ $t('workflow.shiftDetails') }}
      </v-card-title>
      <v-card-text>
        <v-row>
          <v-col cols="12" md="6">
            <v-select
              v-model="shiftDetails.shiftNumber"
              :items="shiftOptions"
              :label="$t('workflow.shift')"
              variant="outlined"
              density="compact"
              :rules="[v => !!v || $t('workflow.shiftRequired')]"
              @update:model-value="emitUpdate"
            />
          </v-col>
          <v-col cols="12" md="6">
            <v-text-field
              v-model="shiftDetails.date"
              :label="$t('common.date')"
              type="date"
              variant="outlined"
              density="compact"
              readonly
            />
          </v-col>
          <v-col cols="12" md="6">
            <v-text-field
              v-model="shiftDetails.startTime"
              :label="$t('workflow.startTime')"
              type="time"
              variant="outlined"
              density="compact"
              :rules="[v => !!v || $t('workflow.startTimeRequired')]"
              @update:model-value="emitUpdate"
            />
          </v-col>
          <v-col cols="12" md="6">
            <v-text-field
              v-model="shiftDetails.supervisor"
              :label="$t('workflow.supervisor')"
              variant="outlined"
              density="compact"
              readonly
            />
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <!-- Pre-Start Checklist Summary -->
    <v-card variant="outlined" class="mb-4">
      <v-card-title class="bg-grey-lighten-4 py-2">
        <v-icon class="mr-2" size="20">mdi-clipboard-check</v-icon>
        {{ $t('workflow.preStartChecklist') }}
      </v-card-title>
      <v-card-text>
        <v-list density="compact">
          <v-list-item v-for="item in checklistItems" :key="item.id">
            <template v-slot:prepend>
              <v-icon :color="item.completed ? 'success' : 'grey'">
                {{ item.completed ? 'mdi-check-circle' : 'mdi-circle-outline' }}
              </v-icon>
            </template>
            <v-list-item-title :class="{ 'text-success': item.completed }">
              {{ item.title }}
            </v-list-item-title>
            <v-list-item-subtitle v-if="item.summary">
              {{ item.summary }}
            </v-list-item-subtitle>
          </v-list-item>
        </v-list>
      </v-card-text>
    </v-card>

    <!-- Shift Notes -->
    <v-textarea
      v-model="shiftDetails.notes"
      :label="$t('workflow.shiftStartNotes')"
      :placeholder="$t('workflow.shiftStartNotesPlaceholder')"
      variant="outlined"
      rows="3"
      class="mb-4"
      @update:model-value="emitUpdate"
    />

    <!-- Final Confirmation -->
    <v-alert
      type="info"
      variant="tonal"
      class="mb-4"
    >
      <v-alert-title>{{ $t('workflow.readyToStartShift') }}</v-alert-title>
      <p class="mb-2">{{ $t('workflow.startShiftDescription') }}</p>
      <ul class="mb-0">
        <li>{{ $t('workflow.createShiftRecord', { date: formatDate(shiftDetails.date) }) }}</li>
        <li>{{ $t('workflow.logAttendance', { count: attendanceCount }) }}</li>
        <li>{{ $t('workflow.setWorkOrdersActive', { count: workOrderCount }) }}</li>
        <li>{{ $t('workflow.enableProductionTracking') }}</li>
      </ul>
    </v-alert>

    <v-checkbox
      v-model="confirmed"
      :disabled="!isFormValid"
      :label="$t('workflow.startShiftConfirmLabel')"
      color="success"
      @update:model-value="handleConfirm"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/authStore'

const { t } = useI18n()

const props = defineProps({
  workflowData: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits(['complete', 'update'])

const authStore = useAuthStore()

// State
const confirmed = ref(false)
const shiftDetails = ref({
  shiftNumber: 1,
  date: new Date().toISOString().split('T')[0],
  startTime: new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' }),
  supervisor: authStore.currentUser?.full_name || 'Unknown',
  notes: ''
})

const shiftOptions = [
  { title: 'Shift 1 (6:00 AM - 2:00 PM)', value: 1 },
  { title: 'Shift 2 (2:00 PM - 10:00 PM)', value: 2 },
  { title: 'Shift 3 (10:00 PM - 6:00 AM)', value: 3 }
]

// Computed
const checklistItems = computed(() => [
  {
    id: 'previous-shift',
    title: t('workflow.previousShiftReview'),
    completed: !!props.workflowData['review-previous']?.isValid,
    summary: props.workflowData['review-previous']?.isValid ? t('workflow.reviewedAndAcknowledged') : t('workflow.notReviewed')
  },
  {
    id: 'attendance',
    title: t('workflow.attendanceConfirmation'),
    completed: !!props.workflowData['confirm-attendance']?.isValid,
    summary: props.workflowData['confirm-attendance']?.presentCount
      ? t('workflow.employeesPresent', { count: props.workflowData['confirm-attendance'].presentCount })
      : t('workflow.notConfirmed')
  },
  {
    id: 'targets',
    title: t('workflow.productionTargetsReview'),
    completed: !!props.workflowData['review-targets']?.isValid,
    summary: props.workflowData['review-targets']?.totalUnits
      ? t('workflow.unitsScheduled', { count: props.workflowData['review-targets'].totalUnits })
      : t('workflow.notReviewed')
  },
  {
    id: 'equipment',
    title: t('workflow.equipmentStatusCheck'),
    completed: !!props.workflowData['check-equipment']?.isValid,
    summary: props.workflowData['check-equipment']?.operationalCount
      ? t('workflow.machinesOperational', { count: props.workflowData['check-equipment'].operationalCount })
      : t('workflow.notChecked')
  }
])

const attendanceCount = computed(() => {
  return props.workflowData['confirm-attendance']?.presentCount || 0
})

const workOrderCount = computed(() => {
  return props.workflowData['review-targets']?.workOrders?.length || 0
})

const isFormValid = computed(() => {
  return shiftDetails.value.shiftNumber &&
         shiftDetails.value.startTime &&
         checklistItems.value.filter(i => !i.completed).length <= 1 // Allow skipping optional steps
})

// Methods
const formatDate = (dateString) => {
  if (!dateString) return ''
  const date = new Date(dateString)
  return date.toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  })
}

const emitUpdate = () => {
  emit('update', {
    shiftDetails: shiftDetails.value,
    isValid: isFormValid.value && confirmed.value
  })
}

const handleConfirm = (value) => {
  if (value && isFormValid.value) {
    emit('complete', {
      ...shiftDetails.value,
      attendanceData: props.workflowData['confirm-attendance'],
      targetsData: props.workflowData['review-targets'],
      equipmentData: props.workflowData['check-equipment']
    })
  }
  emitUpdate()
}

onMounted(() => {
  // Set default shift based on current time
  const hour = new Date().getHours()
  if (hour >= 6 && hour < 14) {
    shiftDetails.value.shiftNumber = 1
  } else if (hour >= 14 && hour < 22) {
    shiftDetails.value.shiftNumber = 2
  } else {
    shiftDetails.value.shiftNumber = 3
  }
})
</script>

<style scoped>
ul {
  padding-left: 20px;
}

ul li {
  margin-bottom: 4px;
}
</style>
