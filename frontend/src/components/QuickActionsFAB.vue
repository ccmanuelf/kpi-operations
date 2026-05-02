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
      {{ t('quickActionsFab.shiftActive') }}
    </v-chip>

    <!-- Shift Info Dialog -->
    <v-dialog v-model="showShiftInfo" max-width="400">
      <v-card>
        <v-card-title class="d-flex align-center">
          <v-icon color="success" class="mr-2">mdi-clock-check</v-icon>
          {{ t('quickActionsFab.activeShift') }}
        </v-card-title>
        <v-card-text>
          <v-list density="compact">
            <v-list-item v-if="activeShift?.shift_number">
              <template v-slot:prepend>
                <v-icon color="grey">mdi-identifier</v-icon>
              </template>
              <v-list-item-title>
                {{ t('quickActionsFab.shiftNumber', { number: activeShift.shift_number }) }}
              </v-list-item-title>
            </v-list-item>
            <v-list-item v-if="activeShift?.start_time">
              <template v-slot:prepend>
                <v-icon color="grey">mdi-clock-start</v-icon>
              </template>
              <v-list-item-title>
                {{ t('quickActionsFab.started', { time: formatTime(activeShift.start_time) }) }}
              </v-list-item-title>
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
          <v-btn variant="text" @click="showShiftInfo = false">{{ t('quickActionsFab.close') }}</v-btn>
          <v-btn color="error" variant="elevated" @click="startEndShift">
            {{ t('quickActionsFab.endShift') }}
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
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/authStore'
import { useWorkflowStore } from '@/stores/workflowStore'
import { useNotificationStore } from '@/stores/notificationStore'
import { useResponsive } from '@/composables/useResponsive'
import WorkflowWizard from './workflow/WorkflowWizard.vue'

const { t } = useI18n()
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

// Define all quick actions. Wrapped in computed() so the action
// labels re-resolve on locale switch (the speed dial tooltips and
// aria-labels read from these labels at runtime).
const allActions = computed(() => [
  {
    id: 'start-shift',
    label: t('quickActionsFab.startShift'),
    icon: 'mdi-play-circle',
    color: 'success',
    requiresNoShift: true,
    action: 'startShift'
  },
  {
    id: 'end-shift',
    label: t('quickActionsFab.endShift'),
    icon: 'mdi-stop-circle',
    color: 'error',
    requiresShift: true,
    action: 'endShift'
  },
  {
    id: 'log-production',
    label: t('quickActionsFab.logProduction'),
    icon: 'mdi-factory',
    color: 'primary',
    route: '/production-entry'
  },
  {
    id: 'report-downtime',
    label: t('quickActionsFab.reportDowntime'),
    icon: 'mdi-clock-alert',
    color: 'warning',
    route: '/data-entry/downtime'
  },
  {
    id: 'quality-entry',
    label: t('quickActionsFab.qualityEntry'),
    icon: 'mdi-check-decagram',
    color: 'info',
    route: '/data-entry/quality'
  },
  {
    id: 'attendance',
    label: t('quickActionsFab.attendance'),
    icon: 'mdi-account-check',
    color: 'secondary',
    route: '/data-entry/attendance'
  }
])

// Filter visible actions based on shift status. allActions is now a
// computed; unwrap via .value to iterate.
const visibleActions = computed(() => {
  return allActions.value.filter(action => {
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
    notificationStore.error(workflowStore.error || t('quickActionsFab.cannotStartShiftWorkflow'))
  }
}

const startEndShift = () => {
  showShiftInfo.value = false
  const success = workflowStore.startWorkflow('shift-end')
  if (success) {
    showWorkflowWizard.value = true
  } else {
    notificationStore.error(workflowStore.error || t('quickActionsFab.cannotStartEndShiftWorkflow'))
  }
}

const onWorkflowComplete = (data) => {
  showWorkflowWizard.value = false
  const message = workflowStore.currentWorkflow === 'shift-start'
    ? t('quickActionsFab.shiftStartedSuccess')
    : t('quickActionsFab.shiftEndedSuccess')
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

/*
 * Stacked above page content (z-index: 5) but BELOW the FAB
 * (z-index: 1000) and BELOW Vuetify v-card chrome that uses an
 * elevation-based stacking context. Previous z-index: 999 was
 * intercepting clicks on AGGridBase toolbar buttons that ended up
 * geometrically under the chip (e.g. Export-CSV on
 * /admin/floating-pool). The chip is purely informational — losing
 * its absolute on-top behavior is acceptable in exchange for not
 * eating button clicks.
 */
.shift-indicator {
  position: fixed;
  bottom: 90px;
  right: 24px;
  cursor: pointer;
  z-index: 5;
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
