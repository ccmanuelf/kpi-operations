<template>
  <div class="quick-actions-fab" v-if="isAuthenticated">
    <!-- Speed Dial FAB -->
    <v-speed-dial
      v-model="isOpen"
      location="bottom end"
      transition="slide-y-reverse-transition"
      :open-on-hover="!isMobile"
    >
      <template v-slot:activator="{ props: activatorProps }">
        <v-fab
          v-bind="activatorProps"
          color="primary"
          icon
          size="large"
          class="fab-main"
          :aria-label="isOpen ? 'Close quick actions' : 'Open quick actions'"
          :aria-expanded="isOpen.toString()"
        >
          <v-icon :class="{ 'rotate-45': isOpen }">
            {{ isOpen ? 'mdi-close' : 'mdi-plus' }}
          </v-icon>
        </v-fab>
      </template>

      <!-- Quick Action Items -->
      <template v-for="action in visibleActions" :key="action.id">
        <v-tooltip :text="action.label" location="start">
          <template v-slot:activator="{ props: tooltipProps }">
            <v-btn
              v-bind="tooltipProps"
              :color="action.color"
              icon
              size="small"
              class="fab-action"
              @click="handleAction(action)"
              :aria-label="action.label"
            >
              <v-icon size="20">{{ action.icon }}</v-icon>
            </v-btn>
          </template>
        </v-tooltip>
      </template>
    </v-speed-dial>

    <!-- Shift Status Indicator -->
    <v-chip
      v-if="hasActiveShift"
      color="success"
      size="small"
      variant="elevated"
      class="shift-indicator"
      @click="showShiftInfo = true"
    >
      <v-icon start size="16">mdi-clock-outline</v-icon>
      Shift Active
    </v-chip>

    <!-- Shift Info Dialog -->
    <v-dialog v-model="showShiftInfo" max-width="400">
      <v-card>
        <v-card-title class="d-flex align-center">
          <v-icon color="success" class="mr-2">mdi-clock-check</v-icon>
          Active Shift
        </v-card-title>
        <v-card-text>
          <v-list density="compact">
            <v-list-item v-if="activeShift?.shift_number">
              <template v-slot:prepend>
                <v-icon color="grey">mdi-identifier</v-icon>
              </template>
              <v-list-item-title>Shift {{ activeShift.shift_number }}</v-list-item-title>
            </v-list-item>
            <v-list-item v-if="activeShift?.start_time">
              <template v-slot:prepend>
                <v-icon color="grey">mdi-clock-start</v-icon>
              </template>
              <v-list-item-title>Started: {{ formatTime(activeShift.start_time) }}</v-list-item-title>
            </v-list-item>
            <v-list-item v-if="activeShift?.supervisor">
              <template v-slot:prepend>
                <v-icon color="grey">mdi-account-tie</v-icon>
              </template>
              <v-list-item-title>{{ activeShift.supervisor }}</v-list-item-title>
            </v-list-item>
          </v-list>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="showShiftInfo = false">Close</v-btn>
          <v-btn color="error" variant="elevated" @click="startEndShift">
            End Shift
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Workflow Wizard -->
    <WorkflowWizard
      v-model="showWorkflowWizard"
      @complete="onWorkflowComplete"
      @cancel="onWorkflowCancel"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/authStore'
import { useWorkflowStore } from '@/stores/workflowStore'
import { useNotificationStore } from '@/stores/notificationStore'
import { useResponsive } from '@/composables/useResponsive'
import WorkflowWizard from './workflow/WorkflowWizard.vue'

const router = useRouter()
const authStore = useAuthStore()
const workflowStore = useWorkflowStore()
const notificationStore = useNotificationStore()
const { isMobile } = useResponsive()

// State
const isOpen = ref(false)
const showShiftInfo = ref(false)
const showWorkflowWizard = ref(false)

// Computed
const isAuthenticated = computed(() => authStore.isAuthenticated)
const hasActiveShift = computed(() => workflowStore.hasActiveShift)
const activeShift = computed(() => workflowStore.activeShift)

// Define all quick actions
const allActions = [
  {
    id: 'start-shift',
    label: 'Start Shift',
    icon: 'mdi-play-circle',
    color: 'success',
    requiresNoShift: true,
    action: 'startShift'
  },
  {
    id: 'end-shift',
    label: 'End Shift',
    icon: 'mdi-stop-circle',
    color: 'error',
    requiresShift: true,
    action: 'endShift'
  },
  {
    id: 'log-production',
    label: 'Log Production',
    icon: 'mdi-factory',
    color: 'primary',
    route: '/production-entry'
  },
  {
    id: 'report-downtime',
    label: 'Report Downtime',
    icon: 'mdi-clock-alert',
    color: 'warning',
    route: '/data-entry/downtime'
  },
  {
    id: 'quality-entry',
    label: 'Quality Entry',
    icon: 'mdi-check-decagram',
    color: 'info',
    route: '/data-entry/quality'
  },
  {
    id: 'attendance',
    label: 'Attendance',
    icon: 'mdi-account-check',
    color: 'secondary',
    route: '/data-entry/attendance'
  }
]

// Filter visible actions based on shift status
const visibleActions = computed(() => {
  return allActions.filter(action => {
    if (action.requiresShift && !hasActiveShift.value) return false
    if (action.requiresNoShift && hasActiveShift.value) return false
    return true
  })
})

// Methods
const handleAction = (action) => {
  isOpen.value = false

  if (action.route) {
    router.push(action.route)
  } else if (action.action === 'startShift') {
    startStartShift()
  } else if (action.action === 'endShift') {
    startEndShift()
  }
}

const startStartShift = () => {
  const success = workflowStore.startWorkflow('shift-start')
  if (success) {
    showWorkflowWizard.value = true
  } else {
    notificationStore.error(workflowStore.error || 'Cannot start shift workflow')
  }
}

const startEndShift = () => {
  showShiftInfo.value = false
  const success = workflowStore.startWorkflow('shift-end')
  if (success) {
    showWorkflowWizard.value = true
  } else {
    notificationStore.error(workflowStore.error || 'Cannot start end shift workflow')
  }
}

const onWorkflowComplete = (data) => {
  showWorkflowWizard.value = false
  const message = workflowStore.currentWorkflow === 'shift-start'
    ? 'Shift started successfully!'
    : 'Shift ended successfully!'
  notificationStore.success(message)
}

const onWorkflowCancel = () => {
  showWorkflowWizard.value = false
}

const formatTime = (timeString) => {
  if (!timeString) return ''
  const date = new Date(timeString)
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit'
  })
}

// Initialize workflow store
onMounted(() => {
  workflowStore.initialize()
})
</script>

<style scoped>
.quick-actions-fab {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 1000;
}

.fab-main {
  transition: transform 0.3s ease;
}

.fab-main:hover {
  transform: scale(1.05);
}

.fab-action {
  margin-bottom: 8px;
}

.rotate-45 {
  transform: rotate(45deg);
  transition: transform 0.3s ease;
}

.shift-indicator {
  position: fixed;
  bottom: 90px;
  right: 24px;
  cursor: pointer;
  z-index: 999;
}

/* Mobile adjustments */
@media (max-width: 600px) {
  .quick-actions-fab {
    bottom: 16px;
    right: 16px;
  }

  .shift-indicator {
    bottom: 82px;
    right: 16px;
  }
}

/* Ensure FAB doesn't overlap with bottom navigation on mobile */
@media (max-width: 960px) {
  .quick-actions-fab {
    bottom: 80px;
  }

  .shift-indicator {
    bottom: 140px;
  }
}
</style>
