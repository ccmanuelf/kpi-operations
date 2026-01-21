<template>
  <v-app>
    <!-- App Bar - Full Width -->
    <v-app-bar v-if="isAuthenticated" color="primary" density="default">
      <v-app-bar-nav-icon @click="drawer = !drawer"></v-app-bar-nav-icon>
      <v-toolbar-title>KPI Platform</v-toolbar-title>
      <v-spacer></v-spacer>

      <v-btn icon @click="toggleShortcutsHelp">
        <v-icon>mdi-keyboard</v-icon>
      </v-btn>
      <v-btn icon @click="logout">
        <v-icon>mdi-logout</v-icon>
      </v-btn>
    </v-app-bar>

    <!-- Navigation Drawer -->
    <v-navigation-drawer
      v-if="isAuthenticated"
      v-model="drawer"
      :rail="rail"
      permanent
    >
      <v-list-item
        prepend-icon="mdi-factory"
        :title="rail ? '' : 'Manufacturing KPI'"
        nav
        @click="rail = !rail"
        class="cursor-pointer"
      >
        <template v-slot:append>
          <v-btn
            :icon="rail ? 'mdi-chevron-right' : 'mdi-chevron-left'"
            variant="text"
            size="small"
            @click.stop="rail = !rail"
          ></v-btn>
        </template>
      </v-list-item>

      <v-divider></v-divider>

      <v-list density="compact" nav>
        <v-list-item prepend-icon="mdi-view-dashboard" title="Dashboard" value="dashboard" to="/" />
        <v-list-item prepend-icon="mdi-factory" title="Production Entry" value="production" to="/production-entry" />
        <v-list-item prepend-icon="mdi-chart-box" title="KPI Dashboard" value="kpi-dashboard" to="/kpi-dashboard" />

        <v-divider class="my-2"></v-divider>
        <v-list-subheader v-if="!rail">DATA ENTRY</v-list-subheader>

        <v-list-item prepend-icon="mdi-clock-alert" title="Downtime" value="downtime" to="/data-entry/downtime" />
        <v-list-item prepend-icon="mdi-account-group" title="Attendance" value="attendance" to="/data-entry/attendance" />
        <v-list-item prepend-icon="mdi-quality-high" title="Quality" value="quality" to="/data-entry/quality" />
        <v-list-item prepend-icon="mdi-pause-circle" title="Hold/Resume" value="hold" to="/data-entry/hold-resume" />

        <v-divider class="my-2"></v-divider>
        <v-list-subheader v-if="!rail">KPI REPORTS</v-list-subheader>

        <v-list-item prepend-icon="mdi-chart-line" title="Efficiency" value="efficiency" to="/kpi/efficiency" />
        <v-list-item prepend-icon="mdi-warehouse" title="WIP Aging" value="wip" to="/kpi/wip-aging" />
        <v-list-item prepend-icon="mdi-truck-delivery" title="On-Time Delivery" value="otd" to="/kpi/on-time-delivery" />
        <v-list-item prepend-icon="mdi-checkbox-marked-circle" title="Availability" value="availability" to="/kpi/availability" />
        <v-list-item prepend-icon="mdi-speedometer" title="Performance" value="performance" to="/kpi/performance" />
        <v-list-item prepend-icon="mdi-star" title="Quality" value="quality-kpi" to="/kpi/quality" />
        <v-list-item prepend-icon="mdi-account-off" title="Absenteeism" value="absenteeism" to="/kpi/absenteeism" />
        <v-list-item prepend-icon="mdi-gauge" title="OEE" value="oee" to="/kpi/oee" />

        <v-divider class="my-2"></v-divider>
        <v-list-subheader v-if="!rail">ADMIN</v-list-subheader>

        <v-list-item prepend-icon="mdi-cog" title="Settings" value="settings" to="/admin/settings" />
        <v-list-item prepend-icon="mdi-account-multiple" title="Users" value="users" to="/admin/users" />
        <v-list-item prepend-icon="mdi-domain" title="Clients" value="clients" to="/admin/clients" />
        <v-list-item prepend-icon="mdi-alert-circle-outline" title="Defect Types" value="defect-types" to="/admin/defect-types" />
      </v-list>
    </v-navigation-drawer>

    <!-- Main Content -->
    <v-main>
      <v-container fluid class="pa-6">
        <router-view />
      </v-container>
    </v-main>

    <!-- Keyboard Shortcuts Help Modal -->
    <KeyboardShortcutsHelp v-model="isHelpModalOpen" />

    <!-- Toast notifications -->
    <v-snackbar
      v-model="showNotification"
      :timeout="2000"
      color="primary"
    >
      {{ notificationMessage }}
    </v-snackbar>
  </v-app>
</template>

<script setup>
import { ref, computed, onMounted, onErrorCaptured } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/authStore'
import { useKeyboardShortcuts } from '@/composables/useKeyboardShortcuts'
import { useKeyboardShortcutsStore } from '@/stores/keyboardShortcutsStore'
import KeyboardShortcutsHelp from '@/components/KeyboardShortcutsHelp.vue'

const router = useRouter()
const authStore = useAuthStore()
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
</style>
