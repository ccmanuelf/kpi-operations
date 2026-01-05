<template>
  <v-app>
    <!-- Mobile Navigation -->
    <MobileNav
      v-if="isMobile && isAuthenticated"
      :shortcuts-enabled="shortcutsEnabled"
      @toggle-shortcuts="toggleShortcutsHelp"
      @logout="logout"
    />

    <!-- Desktop Navigation Drawer -->
    <v-navigation-drawer
      app
      v-model="drawer"
      v-if="!isMobile && isAuthenticated"
      :permanent="isDesktop"
      :temporary="!isDesktop"
    >
      <v-list>
        <v-list-item prepend-icon="mdi-view-dashboard" title="Dashboard" to="/" />
        <v-list-item prepend-icon="mdi-factory" title="Production Entry" to="/production-entry" />
        <v-list-item prepend-icon="mdi-chart-box" title="KPI Dashboard" to="/kpi-dashboard" />

        <v-divider class="my-2"></v-divider>
        <v-list-subheader>Data Entry</v-list-subheader>
        <v-list-item prepend-icon="mdi-clock-alert" title="Downtime" to="/data-entry/downtime" />
        <v-list-item prepend-icon="mdi-account-group" title="Attendance" to="/data-entry/attendance" />
        <v-list-item prepend-icon="mdi-quality-high" title="Quality" to="/data-entry/quality" />
        <v-list-item prepend-icon="mdi-pause-circle" title="Hold/Resume" to="/data-entry/hold-resume" />

        <v-divider class="my-2"></v-divider>
        <v-list-subheader>KPI Reports</v-list-subheader>
        <v-list-item prepend-icon="mdi-chart-line" title="Efficiency" to="/kpi/efficiency" />
        <v-list-item prepend-icon="mdi-warehouse" title="WIP Aging" to="/kpi/wip-aging" />
        <v-list-item prepend-icon="mdi-truck-delivery" title="On-Time Delivery" to="/kpi/on-time-delivery" />
        <v-list-item prepend-icon="mdi-checkbox-marked-circle" title="Availability" to="/kpi/availability" />
        <v-list-item prepend-icon="mdi-speedometer" title="Performance" to="/kpi/performance" />
        <v-list-item prepend-icon="mdi-star" title="Quality" to="/kpi/quality" />
        <v-list-item prepend-icon="mdi-account-off" title="Absenteeism" to="/kpi/absenteeism" />
        <v-list-item prepend-icon="mdi-gauge" title="OEE" to="/kpi/oee" />
      </v-list>
    </v-navigation-drawer>

    <!-- Desktop App Bar -->
    <v-app-bar app v-if="!isMobile && isAuthenticated">
      <v-app-bar-nav-icon
        v-if="isTablet"
        @click="drawer = !drawer"
      ></v-app-bar-nav-icon>
      <v-toolbar-title>KPI Platform</v-toolbar-title>
      <v-spacer></v-spacer>

      <!-- Keyboard shortcuts button -->
      <v-tooltip bottom>
        <template v-slot:activator="{ props }">
          <v-btn
            icon
            v-bind="props"
            @click="toggleShortcutsHelp"
            :color="shortcutsEnabled ? 'primary' : 'grey'"
          >
            <v-icon>mdi-keyboard</v-icon>
          </v-btn>
        </template>
        <span>Keyboard Shortcuts ({{ modifierSymbol }}+/)</span>
      </v-tooltip>

      <v-btn icon @click="logout">
        <v-icon>mdi-logout</v-icon>
      </v-btn>
    </v-app-bar>

    <v-main :class="{ 'mobile-main': isMobile, 'tablet-main': isTablet, 'desktop-main': isDesktop }">
      <v-container
        :fluid="!isDesktop"
        :class="responsiveContainerClass"
      >
        <router-view />
      </v-container>
    </v-main>

    <!-- Keyboard Shortcuts Help Modal -->
    <KeyboardShortcutsHelp v-model="isHelpModalOpen" />

    <!-- Toast notifications for shortcuts -->
    <v-snackbar
      v-model="showNotification"
      :timeout="2000"
      color="primary"
      :location="isMobile ? 'bottom center' : 'bottom right'"
    >
      <div class="d-flex align-center">
        <v-icon class="mr-2">mdi-information</v-icon>
        {{ notificationMessage }}
      </div>
    </v-snackbar>
  </v-app>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/authStore'
import { useKeyboardShortcuts } from '@/composables/useKeyboardShortcuts'
import { useKeyboardShortcutsStore } from '@/stores/keyboardShortcutsStore'
import { useResponsive } from '@/composables/useResponsive'
import KeyboardShortcutsHelp from '@/components/KeyboardShortcutsHelp.vue'
import MobileNav from '@/components/MobileNav.vue'

const router = useRouter()
const authStore = useAuthStore()
const shortcutsStore = useKeyboardShortcutsStore()

// Responsive breakpoints
const { isMobile, isTablet, isDesktop, shouldHideSidebar } = useResponsive()

// Drawer state - hidden by default on mobile/tablet
const drawer = ref(!shouldHideSidebar())
const showNotification = ref(false)
const notificationMessage = ref('')

const {
  isHelpModalOpen,
  toggleHelpModal,
  modifierSymbol
} = useKeyboardShortcuts()

const isAuthenticated = computed(() => authStore.isAuthenticated)
const shortcutsEnabled = computed(() => shortcutsStore.isEnabled)

// Responsive container class
const responsiveContainerClass = computed(() => ({
  'px-2': isMobile.value,
  'px-4': isTablet.value,
  'px-6': isDesktop.value
}))

/**
 * Toggle shortcuts help modal
 */
const toggleShortcutsHelp = () => {
  toggleHelpModal()
}

/**
 * Logout user
 */
const logout = () => {
  authStore.logout()
  router.push('/login')
}

/**
 * Show notification
 */
const notify = (message) => {
  if (!shortcutsStore.preferences.showNotifications) return

  notificationMessage.value = message
  showNotification.value = true
}

/**
 * Setup global shortcut listeners
 */
const setupShortcutListeners = () => {
  // Listen for save events
  window.addEventListener('keyboard-shortcut:save', () => {
    notify('Save triggered')
  })

  // Listen for new entry events
  window.addEventListener('keyboard-shortcut:new', () => {
    notify('New entry triggered')
  })

  // Listen for escape events
  window.addEventListener('keyboard-shortcut:escape', () => {
    if (isHelpModalOpen.value) {
      toggleHelpModal()
    }
  })

  // Listen for refresh events
  window.addEventListener('keyboard-shortcut:refresh', () => {
    notify('Refreshing data...')
    // Emit event for current page to handle
    const event = new CustomEvent('data-refresh')
    window.dispatchEvent(event)
  })
}

onMounted(() => {
  setupShortcutListeners()
})
</script>

<style>
/* Add custom styles for keyboard shortcuts */
.keyboard-shortcut-hint {
  font-size: 11px;
  opacity: 0.7;
  margin-left: 8px;
}

.keyboard-shortcut-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 6px;
  font-size: 10px;
  font-family: monospace;
  background: rgba(0, 0, 0, 0.1);
  border-radius: 3px;
  margin-left: 8px;
}

/* Responsive main content area */
.mobile-main {
  padding-top: 56px !important;
}

.tablet-main {
  padding-top: 64px !important;
}

.desktop-main {
  padding-top: 64px !important;
}

/* Mobile container adjustments */
@media (max-width: 767px) {
  .v-container {
    padding: 12px !important;
  }
}

/* Tablet container adjustments */
@media (min-width: 768px) and (max-width: 1023px) {
  .v-container {
    padding: 16px !important;
  }
}

/* Desktop container adjustments */
@media (min-width: 1024px) {
  .v-container {
    padding: 24px !important;
  }
}
</style>
