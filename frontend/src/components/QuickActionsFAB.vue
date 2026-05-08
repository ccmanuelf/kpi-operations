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
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/authStore'
import { useResponsive } from '@/composables/useResponsive'

const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()
const { isMobile } = useResponsive()

// State
const isOpen = ref(false)

// Computed
const isAuthenticated = computed(() => authStore.isAuthenticated)

// Speed-dial nav shortcuts. Wrapped in computed() so the action labels
// re-resolve on locale switch (the tooltips and aria-labels read from
// these labels at runtime).
const visibleActions = computed(() => [
  {
    id: 'log-production',
    label: t('quickActionsFab.logProduction'),
    icon: 'mdi-factory',
    color: 'primary',
    route: '/production-entry',
  },
  {
    id: 'report-downtime',
    label: t('quickActionsFab.reportDowntime'),
    icon: 'mdi-clock-alert',
    color: 'warning',
    route: '/data-entry/downtime',
  },
  {
    id: 'quality-entry',
    label: t('quickActionsFab.qualityEntry'),
    icon: 'mdi-check-decagram',
    color: 'info',
    route: '/data-entry/quality',
  },
  {
    id: 'attendance',
    label: t('quickActionsFab.attendance'),
    icon: 'mdi-account-check',
    color: 'secondary',
    route: '/data-entry/attendance',
  },
])

// Methods
const handleAction = (action) => {
  isOpen.value = false
  if (action.route) {
    router.push(action.route)
  }
}
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

/* Mobile adjustments */
@media (max-width: 600px) {
  .quick-actions-fab {
    bottom: 16px;
    right: 16px;
  }
}

/* Ensure FAB doesn't overlap with bottom navigation on mobile */
@media (max-width: 960px) {
  .quick-actions-fab {
    bottom: 80px;
  }
}
</style>
