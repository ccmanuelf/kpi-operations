<template>
  <div class="workflow-step-end-shift">
    <!-- Final Confirmation -->
    <v-card variant="outlined" class="mb-4">
      <v-card-title class="bg-error text-white py-3">
        <v-icon class="mr-2" size="24">mdi-stop-circle</v-icon>
        End Shift Confirmation
      </v-card-title>
      <v-card-text class="pt-4">
        <v-alert type="warning" variant="tonal" class="mb-4">
          <v-alert-title>Important</v-alert-title>
          Ending the shift will finalize all data for this shift period.
          Please ensure all entries are complete and accurate.
        </v-alert>

        <!-- Shift Details -->
        <v-card variant="outlined" class="mb-4">
          <v-card-title class="bg-grey-lighten-4 py-2 text-body-1">
            <v-icon class="mr-2" size="20">mdi-calendar-clock</v-icon>
            Shift Details
          </v-card-title>
          <v-card-text>
            <v-row>
              <v-col cols="6">
                <div class="text-caption text-grey">Shift</div>
                <div class="text-body-1">Shift {{ shiftDetails.shiftNumber }}</div>
              </v-col>
              <v-col cols="6">
                <div class="text-caption text-grey">Date</div>
                <div class="text-body-1">{{ formatDate(shiftDetails.date) }}</div>
              </v-col>
              <v-col cols="6">
                <div class="text-caption text-grey">Start Time</div>
                <div class="text-body-1">{{ shiftDetails.startTime }}</div>
              </v-col>
              <v-col cols="6">
                <div class="text-caption text-grey">End Time</div>
                <div class="text-body-1">{{ shiftDetails.endTime }}</div>
              </v-col>
              <v-col cols="6">
                <div class="text-caption text-grey">Duration</div>
                <div class="text-body-1">{{ shiftDetails.duration }}</div>
              </v-col>
              <v-col cols="6">
                <div class="text-caption text-grey">Supervisor</div>
                <div class="text-body-1">{{ shiftDetails.supervisor }}</div>
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>

        <!-- Checklist Summary -->
        <v-card variant="outlined" class="mb-4">
          <v-card-title class="bg-grey-lighten-4 py-2 text-body-1">
            <v-icon class="mr-2" size="20">mdi-clipboard-check</v-icon>
            Pre-Close Checklist
          </v-card-title>
          <v-card-text class="pa-0">
            <v-list density="compact">
              <v-list-item v-for="item in checklistItems" :key="item.id">
                <template v-slot:prepend>
                  <v-icon :color="item.completed ? 'success' : 'error'">
                    {{ item.completed ? 'mdi-check-circle' : 'mdi-alert-circle' }}
                  </v-icon>
                </template>
                <v-list-item-title :class="{ 'text-success': item.completed, 'text-error': !item.completed }">
                  {{ item.title }}
                </v-list-item-title>
                <v-list-item-subtitle>{{ item.summary }}</v-list-item-subtitle>
              </v-list-item>
            </v-list>
          </v-card-text>
        </v-card>

        <!-- End of Shift Notes -->
        <v-textarea
          v-model="endNotes"
          label="End of Shift Notes (Optional)"
          placeholder="Any final notes or comments..."
          variant="outlined"
          rows="3"
          class="mb-4"
          @update:model-value="emitUpdate"
        />

        <!-- Notify Next Shift -->
        <v-checkbox
          v-model="notifyNextShift"
          label="Send notification to incoming shift supervisor"
          color="primary"
          class="mb-2"
        />

        <!-- Final Confirmation -->
        <v-checkbox
          v-model="confirmed"
          :disabled="!allChecksComplete"
          label="I confirm all data has been entered and is accurate. I am ready to end this shift."
          color="error"
          @update:model-value="handleConfirm"
        />

        <v-alert
          v-if="!allChecksComplete"
          type="error"
          variant="tonal"
          density="compact"
          class="mt-2"
        >
          All checklist items must be completed before ending the shift.
        </v-alert>
      </v-card-text>
    </v-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/authStore'
import { useWorkflowStore } from '@/stores/workflowStore'

const props = defineProps({
  workflowData: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits(['complete', 'update'])

const authStore = useAuthStore()
const workflowStore = useWorkflowStore()

// State
const confirmed = ref(false)
const notifyNextShift = ref(true)
const endNotes = ref('')

const shiftDetails = ref({
  shiftNumber: 1,
  date: new Date().toISOString().split('T')[0],
  startTime: '06:00',
  endTime: new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' }),
  duration: '8h 0m',
  supervisor: authStore.currentUser?.full_name || 'Unknown'
})

// Computed
const checklistItems = computed(() => [
  {
    id: 'completeness',
    title: 'Data Completeness Reviewed',
    completed: !!props.workflowData['review-completeness']?.isValid,
    summary: props.workflowData['review-completeness']?.completenessPercentage
      ? `${props.workflowData['review-completeness'].completenessPercentage}% complete`
      : 'Not reviewed'
  },
  {
    id: 'production',
    title: 'Production Entries Complete',
    completed: !!props.workflowData['complete-production']?.isValid,
    summary: props.workflowData['complete-production']?.totalProduced
      ? `${props.workflowData['complete-production'].totalProduced} units produced`
      : 'Pending entries'
  },
  {
    id: 'downtime',
    title: 'Downtime Records Closed',
    completed: !!props.workflowData['close-downtime']?.isValid,
    summary: props.workflowData['close-downtime']?.openCount === 0
      ? 'All incidents resolved'
      : `${props.workflowData['close-downtime']?.openCount || '?'} open incidents`
  },
  {
    id: 'handoff',
    title: 'Handoff Notes Entered',
    completed: !!props.workflowData['enter-handoff']?.isValid,
    summary: props.workflowData['enter-handoff']?.isValid
      ? 'Notes documented'
      : 'Optional'
  },
  {
    id: 'summary',
    title: 'Shift Summary Reviewed',
    completed: !!props.workflowData['generate-summary']?.isValid,
    summary: props.workflowData['generate-summary']?.isValid
      ? 'Summary approved'
      : 'Not reviewed'
  }
])

const allChecksComplete = computed(() => {
  // Required items: completeness, production, downtime, summary
  const required = ['completeness', 'production', 'downtime', 'summary']
  return required.every(id => {
    const item = checklistItems.value.find(i => i.id === id)
    return item?.completed
  })
})

// Methods
const formatDate = (dateString) => {
  if (!dateString) return ''
  const date = new Date(dateString)
  return date.toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    year: 'numeric'
  })
}

const emitUpdate = () => {
  emit('update', {
    endNotes: endNotes.value,
    notifyNextShift: notifyNextShift.value,
    isValid: confirmed.value && allChecksComplete.value
  })
}

const handleConfirm = (value) => {
  if (value && allChecksComplete.value) {
    emit('complete', {
      shiftDetails: shiftDetails.value,
      endNotes: endNotes.value,
      notifyNextShift: notifyNextShift.value,
      productionData: props.workflowData['complete-production'],
      downtimeData: props.workflowData['close-downtime'],
      handoffData: props.workflowData['enter-handoff'],
      summaryData: props.workflowData['generate-summary']
    })
  }
  emitUpdate()
}

// Initialize shift details from active shift
onMounted(() => {
  const activeShift = workflowStore.activeShift
  if (activeShift) {
    shiftDetails.value = {
      shiftNumber: activeShift.shift_number || 1,
      date: activeShift.date || new Date().toISOString().split('T')[0],
      startTime: activeShift.start_time
        ? new Date(activeShift.start_time).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' })
        : '06:00',
      endTime: new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' }),
      duration: calculateDuration(activeShift.start_time),
      supervisor: activeShift.supervisor || authStore.currentUser?.full_name || 'Unknown'
    }
  }
})

const calculateDuration = (startTime) => {
  if (!startTime) return '8h 0m'
  const start = new Date(startTime)
  const now = new Date()
  const diff = now - start
  const hours = Math.floor(diff / (1000 * 60 * 60))
  const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60))
  return `${hours}h ${minutes}m`
}
</script>
