<template>
  <v-app>
    <!-- Skip to main content link for keyboard users -->
    <a href="#main-content" class="skip-to-main sr-only-focusable">
      {{ $t('navigation.skipToMain') }}
    </a>

    <!-- App Bar - Full Width -->
    <v-app-bar v-if="isAuthenticated" color="primary" density="default" role="banner">
      <v-app-bar-nav-icon
        @click="drawer = !drawer"
        :aria-label="$t('navigation.toggleNav')"
        :aria-expanded="drawer.toString()"
      ></v-app-bar-nav-icon>
      <v-toolbar-title>{{ $t('navigation.kpiDashboard') }}</v-toolbar-title>
      <v-spacer></v-spacer>

      <!-- Language Toggle -->
      <LanguageToggle class="mr-2" />

      <v-btn icon @click="toggleShortcutsHelp" :aria-label="$t('common.view') + ' ' + $t('navigation.settings')">
        <v-icon aria-hidden="true">mdi-keyboard</v-icon>
      </v-btn>
      <v-btn icon @click="logout" :aria-label="$t('navigation.logout')">
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
      :aria-label="$t('navigation.mainNav')"
    >
      <v-list-item
        prepend-icon="mdi-factory"
        :title="rail ? '' : $t('navigation.manufacturingKpi')"
        nav
        @click="rail = !rail"
        class="cursor-pointer"
        :aria-label="rail ? $t('navigation.expandNav') : $t('navigation.collapseNav')"
      >
        <template v-slot:append>
          <v-btn
            :icon="rail ? 'mdi-chevron-right' : 'mdi-chevron-left'"
            variant="text"
            size="small"
            @click.stop="rail = !rail"
            :aria-label="rail ? $t('navigation.expandNav') : $t('navigation.collapseNav')"
          ></v-btn>
        </template>
      </v-list-item>

      <v-divider role="separator"></v-divider>

      <v-list density="compact" nav :aria-label="$t('navigation.primaryNav')">
        <v-list-item prepend-icon="mdi-view-dashboard" :title="$t('navigation.dashboard')" value="dashboard" to="/" />
        <v-list-item prepend-icon="mdi-account-hard-hat" :title="$t('navigation.myShift')" value="my-shift" to="/my-shift" />
        <v-list-item prepend-icon="mdi-clipboard-list" :title="$t('navigation.workOrders')" value="work-orders" to="/work-orders" />
        <v-list-item prepend-icon="mdi-factory" :title="$t('navigation.productionEntry')" value="production" to="/production-entry" />
        <v-list-item prepend-icon="mdi-chart-box" :title="$t('navigation.kpiDashboard')" value="kpi-dashboard" to="/kpi-dashboard" />

        <v-divider class="my-2" role="separator"></v-divider>
        <v-list-subheader v-if="!rail" id="data-entry-nav">{{ $t('navigation.dataEntry').toUpperCase() }}</v-list-subheader>

        <v-list-item prepend-icon="mdi-clock-alert" :title="$t('navigation.downtime')" value="downtime" to="/data-entry/downtime" />
        <v-list-item prepend-icon="mdi-account-group" :title="$t('navigation.attendance')" value="attendance" to="/data-entry/attendance" />
        <v-list-item prepend-icon="mdi-quality-high" :title="$t('navigation.quality')" value="quality" to="/data-entry/quality" />
        <v-list-item prepend-icon="mdi-pause-circle" :title="$t('navigation.holdResume')" value="hold" to="/data-entry/hold-resume" />

        <v-divider class="my-2" role="separator"></v-divider>
        <v-list-subheader v-if="!rail" id="kpi-reports-nav">{{ $t('navigation.kpiReports').toUpperCase() }}</v-list-subheader>

        <v-list-item prepend-icon="mdi-chart-line" :title="$t('kpi.efficiency')" value="efficiency" to="/kpi/efficiency" />
        <v-list-item prepend-icon="mdi-warehouse" :title="$t('kpi.wipAging')" value="wip" to="/kpi/wip-aging" />
        <v-list-item prepend-icon="mdi-truck-delivery" :title="$t('kpi.otdFull')" value="otd" to="/kpi/on-time-delivery" />
        <v-list-item prepend-icon="mdi-checkbox-marked-circle" :title="$t('kpi.availability')" value="availability" to="/kpi/availability" />
        <v-list-item prepend-icon="mdi-speedometer" :title="$t('kpi.performance')" value="performance" to="/kpi/performance" />
        <v-list-item prepend-icon="mdi-star" :title="$t('navigation.quality')" value="quality-kpi" to="/kpi/quality" />
        <v-list-item prepend-icon="mdi-account-off" :title="$t('kpi.absenteeism')" value="absenteeism" to="/kpi/absenteeism" />
        <v-list-item prepend-icon="mdi-gauge" title="OEE" value="oee" to="/kpi/oee" />

        <v-divider class="my-2" role="separator"></v-divider>
        <v-list-subheader v-if="!rail" id="tools-nav">{{ $t('navigation.tools').toUpperCase() }}</v-list-subheader>

        <v-list-item prepend-icon="mdi-bell-alert" :title="$t('navigation.alerts')" value="alerts" to="/alerts" />
        <v-list-item prepend-icon="mdi-calculator-variant" :title="$t('navigation.simulation')" value="simulation" to="/simulation" />

        <v-divider class="my-2" role="separator"></v-divider>
        <v-list-subheader v-if="!rail" id="admin-nav">{{ $t('navigation.admin').toUpperCase() }}</v-list-subheader>

        <v-list-item prepend-icon="mdi-cog" :title="$t('navigation.settings')" value="settings" to="/admin/settings" />
        <v-list-item prepend-icon="mdi-account-multiple" :title="$t('navigation.users')" value="users" to="/admin/users" />
        <v-list-item prepend-icon="mdi-domain" :title="$t('navigation.clients')" value="clients" to="/admin/clients" />
        <v-list-item prepend-icon="mdi-alert-circle-outline" :title="$t('navigation.defectTypes')" value="defect-types" to="/admin/defect-types" />
        <v-list-item prepend-icon="mdi-tune-variant" :title="$t('navigation.clientConfig')" value="client-config" to="/admin/client-config" />
        <v-list-item prepend-icon="mdi-chart-scatter-plot" :title="$t('navigation.partOpportunities')" value="part-opportunities" to="/admin/part-opportunities" />
        <v-list-item prepend-icon="mdi-account-switch" :title="$t('navigation.floatingPool')" value="floating-pool" to="/admin/floating-pool" />
        <v-list-item prepend-icon="mdi-sitemap" :title="$t('navigation.workflowConfig')" value="workflow-config" to="/admin/workflow-config" />
        <v-list-item prepend-icon="mdi-database-cog" :title="$t('navigation.databaseConfig')" value="database-config" to="/admin/database" />
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
          :aria-label="$t('common.close')"
        >
          {{ $t('common.close') }}
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
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/authStore'
import { useNotificationStore } from '@/stores/notificationStore'
import { useKeyboardShortcuts } from '@/composables/useKeyboardShortcuts'
import { useKeyboardShortcutsStore } from '@/stores/keyboardShortcutsStore'
import KeyboardShortcutsHelp from '@/components/KeyboardShortcutsHelp.vue'
import QuickActionsFAB from '@/components/QuickActionsFAB.vue'
import LanguageToggle from '@/components/LanguageToggle.vue'

const { t } = useI18n()
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
