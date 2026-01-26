<template>
  <div v-if="isMobile" class="mobile-nav" role="banner">
    <!-- Mobile Header -->
    <div class="mobile-header">
      <v-app-bar color="primary" dark prominent>
        <v-app-bar-nav-icon
          @click="toggleDrawer"
          :aria-label="$t('navigation.toggleNav')"
          :aria-expanded="drawer.toString()"
          aria-controls="mobile-nav-drawer"
        ></v-app-bar-nav-icon>
        <v-toolbar-title>{{ $t('navigation.kpiDashboard') }}</v-toolbar-title>
        <v-spacer></v-spacer>

        <!-- Keyboard shortcuts button (smaller on mobile) -->
        <v-btn
          icon
          size="small"
          @click="$emit('toggle-shortcuts')"
          :color="shortcutsEnabled ? 'white' : 'grey'"
          :aria-label="$t('navigation.settings')"
          :aria-pressed="shortcutsEnabled.toString()"
        >
          <v-icon size="small">mdi-keyboard</v-icon>
        </v-btn>

        <v-btn icon size="small" @click="$emit('logout')" :aria-label="$t('navigation.logout')">
          <v-icon size="small">mdi-logout</v-icon>
        </v-btn>
      </v-app-bar>
    </div>

    <!-- Mobile Navigation Drawer -->
    <v-navigation-drawer
      id="mobile-nav-drawer"
      v-model="drawer"
      temporary
      touchless
      width="280"
      class="mobile-drawer"
      role="navigation"
      :aria-label="$t('navigation.mainNav')"
    >
      <!-- User Info Section -->
      <div class="mobile-user-section">
        <v-avatar color="primary" size="48">
          <v-icon color="white">mdi-account</v-icon>
        </v-avatar>
        <div class="user-name">User</div>
      </div>

      <!-- Navigation List -->
      <v-list nav class="mobile-nav-list" :aria-label="$t('navigation.primaryNav')">
        <!-- Main Navigation -->
        <v-list-item
          v-for="item in mainNavItems"
          :key="item.to"
          :to="item.to"
          :prepend-icon="item.icon"
          :title="item.title"
          @click="closeDrawer"
          class="mobile-nav-item"
          :aria-label="`Navigate to ${item.title}`"
        />

        <!-- Data Entry Section -->
        <v-divider class="my-2" role="separator"></v-divider>
        <v-list-subheader id="data-entry-heading" class="mobile-section-header">
          {{ $t('navigation.dataEntry') }}
        </v-list-subheader>
        <v-list-item
          v-for="item in dataEntryItems"
          :key="item.to"
          :to="item.to"
          :prepend-icon="item.icon"
          :title="item.title"
          @click="closeDrawer"
          class="mobile-nav-item"
          :aria-label="`Navigate to ${item.title} data entry`"
        />

        <!-- KPI Reports Section -->
        <v-divider class="my-2" role="separator"></v-divider>
        <v-list-subheader id="kpi-reports-heading" class="mobile-section-header">
          {{ $t('navigation.kpiReports') }}
        </v-list-subheader>
        <v-list-item
          v-for="item in kpiReportItems"
          :key="item.to"
          :to="item.to"
          :prepend-icon="item.icon"
          :title="item.title"
          @click="closeDrawer"
          class="mobile-nav-item"
          :aria-label="`View ${item.title} KPI report`"
        />
      </v-list>

      <!-- Logout Button at Bottom -->
      <template v-slot:append>
        <div class="mobile-logout-section">
          <v-btn
            block
            color="error"
            variant="outlined"
            @click="handleLogout"
            class="mobile-logout-btn"
            :aria-label="$t('navigation.logout')"
          >
            <v-icon left aria-hidden="true">mdi-logout</v-icon>
            {{ $t('navigation.logout') }}
          </v-btn>
        </div>
      </template>
    </v-navigation-drawer>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useResponsive } from '@/composables/useResponsive'

const { t } = useI18n()

const props = defineProps({
  shortcutsEnabled: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['toggle-shortcuts', 'logout'])

const { isMobile } = useResponsive()
const drawer = ref(false)

// Navigation items with i18n support
const mainNavItems = computed(() => [
  { title: t('navigation.dashboard'), icon: 'mdi-view-dashboard', to: '/' },
  { title: t('navigation.productionEntry'), icon: 'mdi-factory', to: '/production-entry' },
  { title: t('navigation.kpiDashboard'), icon: 'mdi-chart-box', to: '/kpi-dashboard' }
])

const dataEntryItems = computed(() => [
  { title: t('navigation.downtime'), icon: 'mdi-clock-alert', to: '/data-entry/downtime' },
  { title: t('navigation.attendance'), icon: 'mdi-account-group', to: '/data-entry/attendance' },
  { title: t('navigation.quality'), icon: 'mdi-quality-high', to: '/data-entry/quality' },
  { title: t('navigation.holdResume'), icon: 'mdi-pause-circle', to: '/data-entry/hold-resume' }
])

const kpiReportItems = computed(() => [
  { title: t('kpi.efficiency'), icon: 'mdi-chart-line', to: '/kpi/efficiency' },
  { title: t('kpi.wipAging'), icon: 'mdi-warehouse', to: '/kpi/wip-aging' },
  { title: t('kpi.otdFull'), icon: 'mdi-truck-delivery', to: '/kpi/on-time-delivery' },
  { title: t('kpi.availability'), icon: 'mdi-checkbox-marked-circle', to: '/kpi/availability' },
  { title: t('kpi.performance'), icon: 'mdi-speedometer', to: '/kpi/performance' },
  { title: t('navigation.quality'), icon: 'mdi-star', to: '/kpi/quality' },
  { title: t('kpi.absenteeism'), icon: 'mdi-account-off', to: '/kpi/absenteeism' },
  { title: 'OEE', icon: 'mdi-gauge', to: '/kpi/oee' }
])

const toggleDrawer = () => {
  drawer.value = !drawer.value
}

const closeDrawer = () => {
  drawer.value = false
}

const handleLogout = () => {
  closeDrawer()
  emit('logout')
}
</script>

<style scoped>
.mobile-nav {
  width: 100%;
}

.mobile-header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 1000;
}

.mobile-drawer {
  background: white;
}

.mobile-user-section {
  padding: 24px 16px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.user-name {
  font-size: 16px;
  font-weight: 500;
}

.mobile-nav-list {
  padding: 8px 0;
}

.mobile-section-header {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  color: rgba(0, 0, 0, 0.6);
  padding: 12px 16px 8px;
}

.mobile-nav-item {
  min-height: 48px;
  padding: 12px 16px;
  margin: 4px 8px;
  border-radius: 8px;
  transition: background-color 0.2s;
}

.mobile-nav-item:active {
  background-color: rgba(0, 0, 0, 0.05);
}

.mobile-logout-section {
  padding: 16px;
  border-top: 1px solid rgba(0, 0, 0, 0.12);
}

.mobile-logout-btn {
  min-height: 44px;
  font-weight: 500;
}

/* Touch-friendly hit areas */
:deep(.v-btn) {
  min-height: 44px;
  min-width: 44px;
}

/* Smooth drawer animation */
:deep(.v-navigation-drawer__scrim) {
  backdrop-filter: blur(2px);
}
</style>
