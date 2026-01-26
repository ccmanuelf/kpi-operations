<template>
  <v-app>
    <!-- Skip to main content link for keyboard users -->
    <a href="#main-content" class="skip-to-main sr-only-focusable">
      Skip to main content
    </a>

    <!-- App Bar - Full Width -->
    <v-app-bar v-if="isAuthenticated" color="primary" density="default" role="banner">
      <v-app-bar-nav-icon
        @click="drawer = !drawer"
        aria-label="Toggle navigation menu"
        :aria-expanded="drawer.toString()"
      ></v-app-bar-nav-icon>
      <v-toolbar-title>KPI Platform</v-toolbar-title>
      <v-spacer></v-spacer>

      <v-btn icon @click="toggleShortcutsHelp" aria-label="View keyboard shortcuts">
        <v-icon aria-hidden="true">mdi-keyboard</v-icon>
      </v-btn>
      <v-btn icon @click="logout" aria-label="Logout from application">
        <v-icon aria-hidden="true">mdi-logout</v-icon>
      </v-btn>
    </v-app-bar>

    <!-- Navigation Drawer -->
    <v-navigation-drawer
      v-if="isAuthenticated"
      v-model="drawer"
      :rail="rail"
      permanent
      role="navigation"
      aria-label="Main navigation"
    >
      <v-list-item
        prepend-icon="mdi-factory"
        :title="rail ? '' : 'Manufacturing KPI'"
        nav
        @click="rail = !rail"
        class="cursor-pointer"
        :aria-label="rail ? 'Expand navigation' : 'Collapse navigation'"
      >
        <template v-slot:append>
          <v-btn
            :icon="rail ? 'mdi-chevron-right' : 'mdi-chevron-left'"
            variant="text"
            size="small"
            @click.stop="rail = !rail"
            :aria-label="rail ? 'Expand navigation sidebar' : 'Collapse navigation sidebar'"
          ></v-btn>
        </template>
      </v-list-item>

      <v-divider role="separator"></v-divider>

      <v-list density="compact" nav aria-label="Primary navigation">
        <v-list-item prepend-icon="mdi-view-dashboard" title="Dashboard" value="dashboard" to="/" aria-label="Go to Dashboard" />
        <v-list-item prepend-icon="mdi-account-hard-hat" title="My Shift" value="my-shift" to="/my-shift" aria-label="Go to My Shift Dashboard - personalized operator view" />
        <v-list-item prepend-icon="mdi-clipboard-list" title="Work Orders" value="work-orders" to="/work-orders" aria-label="Go to Work Order Management" />
        <v-list-item prepend-icon="mdi-factory" title="Production Entry" value="production" to="/production-entry" aria-label="Go to Production Entry" />
        <v-list-item prepend-icon="mdi-chart-box" title="KPI Dashboard" value="kpi-dashboard" to="/kpi-dashboard" aria-label="Go to KPI Dashboard" />

        <v-divider class="my-2" role="separator"></v-divider>
        <v-list-subheader v-if="!rail" id="data-entry-nav">DATA ENTRY</v-list-subheader>

        <v-list-item prepend-icon="mdi-clock-alert" title="Downtime" value="downtime" to="/data-entry/downtime" aria-label="Go to Downtime data entry" />
        <v-list-item prepend-icon="mdi-account-group" title="Attendance" value="attendance" to="/data-entry/attendance" aria-label="Go to Attendance data entry" />
        <v-list-item prepend-icon="mdi-quality-high" title="Quality" value="quality" to="/data-entry/quality" aria-label="Go to Quality data entry" />
        <v-list-item prepend-icon="mdi-pause-circle" title="Hold/Resume" value="hold" to="/data-entry/hold-resume" aria-label="Go to Hold and Resume data entry" />

        <v-divider class="my-2" role="separator"></v-divider>
        <v-list-subheader v-if="!rail" id="kpi-reports-nav">KPI REPORTS</v-list-subheader>

        <v-list-item prepend-icon="mdi-chart-line" title="Efficiency" value="efficiency" to="/kpi/efficiency" aria-label="View Efficiency KPI report" />
        <v-list-item prepend-icon="mdi-warehouse" title="WIP Aging" value="wip" to="/kpi/wip-aging" aria-label="View WIP Aging KPI report" />
        <v-list-item prepend-icon="mdi-truck-delivery" title="On-Time Delivery" value="otd" to="/kpi/on-time-delivery" aria-label="View On-Time Delivery KPI report" />
        <v-list-item prepend-icon="mdi-checkbox-marked-circle" title="Availability" value="availability" to="/kpi/availability" aria-label="View Availability KPI report" />
        <v-list-item prepend-icon="mdi-speedometer" title="Performance" value="performance" to="/kpi/performance" aria-label="View Performance KPI report" />
        <v-list-item prepend-icon="mdi-star" title="Quality" value="quality-kpi" to="/kpi/quality" aria-label="View Quality KPI report" />
        <v-list-item prepend-icon="mdi-account-off" title="Absenteeism" value="absenteeism" to="/kpi/absenteeism" aria-label="View Absenteeism KPI report" />
        <v-list-item prepend-icon="mdi-gauge" title="OEE" value="oee" to="/kpi/oee" aria-label="View OEE KPI report" />

        <v-divider class="my-2" role="separator"></v-divider>
        <v-list-subheader v-if="!rail" id="admin-nav">ADMIN</v-list-subheader>

        <v-list-item prepend-icon="mdi-cog" title="Settings" value="settings" to="/admin/settings" aria-label="Go to Settings" />
        <v-list-item prepend-icon="mdi-account-multiple" title="Users" value="users" to="/admin/users" aria-label="Go to User management" />
        <v-list-item prepend-icon="mdi-domain" title="Clients" value="clients" to="/admin/clients" aria-label="Go to Client management" />
        <v-list-item prepend-icon="mdi-alert-circle-outline" title="Defect Types" value="defect-types" to="/admin/defect-types" aria-label="Go to Defect Types management" />
      </v-list>
    </v-navigation-drawer>

    <!-- Main Content -->
    <v-main id="main-content" role="main" aria-label="Main content">
      <v-container fluid class="pa-6">
        <router-view />
      </v-container>
    </v-main>

    <!-- Keyboard Shortcuts Help Modal -->
    <KeyboardShortcutsHelp v-model="isHelpModalOpen" />

    <!-- Toast notifications for keyboard shortcuts -->
    <v-snackbar
      v-model="showNotification"
      :timeout="2000"
      color="primary"
      role="status"
      aria-live="polite"
    >
      {{ notificationMessage }}
    </v-snackbar>

    <!-- Global notifications from notification store -->
    <v-snackbar
      v-model="notificationStore.snackbar.show"
      :timeout="notificationStore.snackbar.timeout"
      :color="notificationStore.snackbar.color"
      location="bottom right"
      role="alert"
      aria-live="assertive"
    >
      {{ notificationStore.snackbar.message }}
      <template v-slot:actions>
        <v-btn
          variant="text"
          size="small"
          @click="notificationStore.hide()"
          aria-label="Close notification"
        >
          Close
        </v-btn>
      </template>
    </v-snackbar>

    <!-- Quick Actions FAB for Workflow Navigation -->
    <QuickActionsFAB v-if="isAuthenticated" />
  </v-app>
</template>

<script setup>
import { ref, computed, onMounted, onErrorCaptured } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/authStore'
import { useNotificationStore } from '@/stores/notificationStore'
import { useKeyboardShortcuts } from '@/composables/useKeyboardShortcuts'
import { useKeyboardShortcutsStore } from '@/stores/keyboardShortcutsStore'
import KeyboardShortcutsHelp from '@/components/KeyboardShortcutsHelp.vue'
import QuickActionsFAB from '@/components/QuickActionsFAB.vue'

const router = useRouter()
const authStore = useAuthStore()
const notificationStore = useNotificationStore()
const shortcutsStore = useKeyboardShortcutsStore()

// Error handling for child components
onErrorCaptured((err, instance, info) => {
  console.error('Component Error:', err)
  console.error('Error Info:', info)
  // Return false to prevent the error from propagating
  return false
})

// Drawer state
const drawer = ref(true)
const rail = ref(false)
const showNotification = ref(false)
const notificationMessage = ref('')

const {
  isHelpModalOpen,
  toggleHelpModal
} = useKeyboardShortcuts()

const isAuthenticated = computed(() => authStore.isAuthenticated)

const toggleShortcutsHelp = () => {
  toggleHelpModal()
}

const logout = () => {
  authStore.logout()
  router.push('/login')
}

const notify = (message) => {
  if (!shortcutsStore.preferences?.showNotifications) return
  notificationMessage.value = message
  showNotification.value = true
}

const setupShortcutListeners = () => {
  window.addEventListener('keyboard-shortcut:save', () => notify('Save triggered'))
  window.addEventListener('keyboard-shortcut:new', () => notify('New entry triggered'))
  window.addEventListener('keyboard-shortcut:escape', () => {
    if (isHelpModalOpen.value) toggleHelpModal()
  })
  window.addEventListener('keyboard-shortcut:refresh', () => {
    notify('Refreshing data...')
    window.dispatchEvent(new CustomEvent('data-refresh'))
  })
}

onMounted(() => {
  setupShortcutListeners()
})
</script>

<style>
/* Vuetify 3 layout - let framework handle positioning */
.v-application {
  min-height: 100vh;
}

/* Ensure main content doesn't overlap sidebar */
.v-main {
  min-height: 100vh;
}

/* Smooth transition when rail mode toggles */
.v-navigation-drawer {
  transition: width 0.2s ease-in-out !important;
}

/* Clickable list item for expand/collapse */
.cursor-pointer {
  cursor: pointer;
}

/* Make the expand button visible in rail mode */
.v-navigation-drawer--rail .v-list-item .v-btn {
  margin-left: -8px;
}

/* Ensure navigation drawer content is scrollable */
.v-navigation-drawer .v-list {
  overflow-y: auto !important;
  max-height: calc(100vh - 120px) !important;
}

/* Route transition animations */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Enhanced route transitions */
.slide-fade-enter-active {
  transition: all 0.2s ease-out;
}

.slide-fade-leave-active {
  transition: all 0.15s ease-in;
}

.slide-fade-enter-from {
  opacity: 0;
  transform: translateY(8px);
}

.slide-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

/* Active navigation item enhancement */
.v-navigation-drawer .v-list-item--active {
  position: relative;
}

.v-navigation-drawer .v-list-item--active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 8px;
  bottom: 8px;
  width: 3px;
  background-color: var(--cds-blue-60);
  border-radius: 0 2px 2px 0;
}

/* App bar action buttons hover */
.v-app-bar .v-btn:hover {
  background-color: rgba(255, 255, 255, 0.1) !important;
}

/* Main content area padding for mobile */
@media (max-width: 600px) {
  .v-main > .v-container {
    padding: var(--cds-spacing-03) !important;
  }
}

/* Snackbar positioning for mobile nav */
@media (max-width: 600px) {
  .v-snackbar {
    bottom: 80px !important;
  }
}
</style>
