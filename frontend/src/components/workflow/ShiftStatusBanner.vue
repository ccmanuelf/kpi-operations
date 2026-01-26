<template>
  <v-alert
    v-if="showBanner"
    :type="alertType"
    variant="tonal"
    prominent
    class="mb-4"
  >
    <template v-slot:prepend>
      <v-icon :icon="alertIcon" size="28" />
    </template>

    <v-alert-title class="text-h6">{{ alertTitle }}</v-alert-title>

    <template v-if="hasActiveShift">
      <p class="mb-2">
        Shift {{ activeShift?.shift_number || '1' }} has been active since
        {{ formatTime(activeShift?.start_time) }}.
        <span v-if="shiftDuration" class="font-weight-medium">
          ({{ shiftDuration }})
        </span>
      </p>
      <div class="d-flex gap-2 flex-wrap">
        <v-btn
          color="primary"
          variant="elevated"
          size="small"
          @click="emit('end-shift')"
        >
          <v-icon start>mdi-stop-circle</v-icon>
          End Shift
        </v-btn>
        <v-btn
          variant="outlined"
          size="small"
          @click="showDetails = true"
        >
          View Shift Details
        </v-btn>
      </div>
    </template>

    <template v-else>
      <p class="mb-2">
        No active shift. Start a shift to begin tracking production and attendance.
      </p>
      <v-btn
        color="success"
        variant="elevated"
        size="small"
        @click="emit('start-shift')"
      >
        <v-icon start>mdi-play-circle</v-icon>
        Start Shift
      </v-btn>
    </template>

    <template v-slot:append>
      <v-btn
        icon
        variant="text"
        size="small"
        @click="dismissBanner"
        aria-label="Dismiss banner"
      >
        <v-icon>mdi-close</v-icon>
      </v-btn>
    </template>
  </v-alert>

  <!-- Shift Details Dialog -->
  <v-dialog v-model="showDetails" max-width="500">
    <v-card v-if="activeShift">
      <v-card-title class="d-flex align-center bg-primary text-white">
        <v-icon class="mr-2">mdi-clock-check</v-icon>
        Active Shift Details
      </v-card-title>
      <v-card-text class="pt-4">
        <v-list density="compact">
          <v-list-item>
            <template v-slot:prepend>
              <v-icon color="grey">mdi-identifier</v-icon>
            </template>
            <v-list-item-title>Shift Number</v-list-item-title>
            <template v-slot:append>
              <span class="font-weight-medium">Shift {{ activeShift.shift_number || 1 }}</span>
            </template>
          </v-list-item>

          <v-list-item>
            <template v-slot:prepend>
              <v-icon color="grey">mdi-calendar</v-icon>
            </template>
            <v-list-item-title>Date</v-list-item-title>
            <template v-slot:append>
              <span>{{ formatDate(activeShift.date) }}</span>
            </template>
          </v-list-item>

          <v-list-item>
            <template v-slot:prepend>
              <v-icon color="grey">mdi-clock-start</v-icon>
            </template>
            <v-list-item-title>Start Time</v-list-item-title>
            <template v-slot:append>
              <span>{{ formatTime(activeShift.start_time) }}</span>
            </template>
          </v-list-item>

          <v-list-item>
            <template v-slot:prepend>
              <v-icon color="grey">mdi-timer-outline</v-icon>
            </template>
            <v-list-item-title>Duration</v-list-item-title>
            <template v-slot:append>
              <span class="text-primary font-weight-medium">{{ shiftDuration }}</span>
            </template>
          </v-list-item>

          <v-list-item v-if="activeShift.supervisor">
            <template v-slot:prepend>
              <v-icon color="grey">mdi-account-tie</v-icon>
            </template>
            <v-list-item-title>Supervisor</v-list-item-title>
            <template v-slot:append>
              <span>{{ activeShift.supervisor }}</span>
            </template>
          </v-list-item>
        </v-list>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="showDetails = false">Close</v-btn>
        <v-btn color="error" variant="elevated" @click="handleEndShift">
          End Shift
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useWorkflowStore } from '@/stores/workflowStore'

const emit = defineEmits(['start-shift', 'end-shift'])

const workflowStore = useWorkflowStore()

// State
const dismissed = ref(false)
const showDetails = ref(false)
const currentTime = ref(new Date())
let timeInterval = null

// Computed
const activeShift = computed(() => workflowStore.activeShift)
const hasActiveShift = computed(() => workflowStore.hasActiveShift)

const showBanner = computed(() => {
  if (dismissed.value) return false
  // Always show if no shift is active (prompt to start)
  // Or show if shift has been active for a while (reminder)
  return true
})

const alertType = computed(() => {
  if (!hasActiveShift.value) return 'info'
  return 'success'
})

const alertIcon = computed(() => {
  if (!hasActiveShift.value) return 'mdi-information'
  return 'mdi-clock-check-outline'
})

const alertTitle = computed(() => {
  if (!hasActiveShift.value) return 'Ready to Start Shift?'
  return 'Shift in Progress'
})

const shiftDuration = computed(() => {
  if (!activeShift.value?.start_time) return ''

  const start = new Date(activeShift.value.start_time)
  const diff = currentTime.value - start

  const hours = Math.floor(diff / (1000 * 60 * 60))
  const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60))

  if (hours === 0) return `${minutes}m`
  return `${hours}h ${minutes}m`
})

// Methods
const formatTime = (timeString) => {
  if (!timeString) return ''
  const date = new Date(timeString)
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit'
  })
}

const formatDate = (dateString) => {
  if (!dateString) return new Date().toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric'
  })
  const date = new Date(dateString)
  return date.toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric'
  })
}

const dismissBanner = () => {
  dismissed.value = true
  // Re-show after 1 hour
  setTimeout(() => {
    dismissed.value = false
  }, 60 * 60 * 1000)
}

const handleEndShift = () => {
  showDetails.value = false
  emit('end-shift')
}

// Update time every minute for duration calculation
onMounted(() => {
  workflowStore.initialize()
  timeInterval = setInterval(() => {
    currentTime.value = new Date()
  }, 60000)
})

onUnmounted(() => {
  if (timeInterval) {
    clearInterval(timeInterval)
  }
})
</script>

<style scoped>
.gap-2 {
  gap: 8px;
}
</style>
