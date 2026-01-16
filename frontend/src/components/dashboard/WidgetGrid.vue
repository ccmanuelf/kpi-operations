<template>
  <div class="widget-grid-wrapper">
    <!-- Edit Mode Toolbar -->
    <v-toolbar
      v-if="isEditing"
      color="primary"
      density="compact"
      class="mb-4 rounded"
    >
      <v-icon class="ml-4">mdi-drag</v-icon>
      <v-toolbar-title class="text-body-1">
        Drag widgets to reorder
      </v-toolbar-title>
      <v-spacer />
      <v-btn
        variant="text"
        prepend-icon="mdi-plus"
        @click="$emit('addWidget')"
      >
        Add Widget
      </v-btn>
      <v-btn
        variant="text"
        prepend-icon="mdi-check"
        @click="$emit('finishEditing')"
      >
        Done
      </v-btn>
    </v-toolbar>

    <!-- Empty State -->
    <div v-if="widgets.length === 0" class="empty-state text-center py-16">
      <v-icon size="80" color="grey-lighten-1">mdi-view-dashboard-outline</v-icon>
      <h3 class="text-h5 text-grey mt-4">No Widgets</h3>
      <p class="text-body-2 text-grey-darken-1 mt-2">
        Add widgets to customize your dashboard
      </p>
      <v-btn
        color="primary"
        variant="flat"
        class="mt-4"
        prepend-icon="mdi-plus"
        @click="$emit('addWidget')"
      >
        Add Widget
      </v-btn>
    </div>

    <!-- Draggable Widget Grid -->
    <draggable
      v-else
      v-model="localWidgets"
      :disabled="!isEditing"
      item-key="widget_key"
      handle=".drag-handle"
      ghost-class="widget-ghost"
      drag-class="widget-dragging"
      :animation="200"
      :class="gridClass"
      @end="onDragEnd"
    >
      <template #item="{ element }">
        <div :class="itemClass">
          <WidgetContainer
            :widget="element"
            :is-editing="isEditing"
            :layout="layout"
            @remove="removeWidget(element.widget_key)"
            @hide="hideWidget(element.widget_key)"
            @refresh="$emit('refreshWidget', element.widget_key)"
            @settings="$emit('widgetSettings', element.widget_key)"
            @fullscreen="$emit('widgetFullscreen', element.widget_key)"
          >
            <!-- Dynamic Widget Component -->
            <component
              v-if="!isEditing"
              :is="getWidgetComponent(element.widget_key)"
              v-bind="getWidgetProps(element)"
              @viewDetails="$emit('widgetViewDetails', element.widget_key)"
            />
          </WidgetContainer>
        </div>
      </template>
    </draggable>

    <!-- Loading Overlay -->
    <v-overlay
      :model-value="loading"
      contained
      class="align-center justify-center"
    >
      <v-progress-circular indeterminate color="primary" size="64" />
    </v-overlay>
  </div>
</template>

<script setup>
import { ref, computed, watch, defineAsyncComponent } from 'vue'
import draggable from 'vuedraggable'
import { useDashboardStore } from '@/stores/dashboardStore'
import WidgetContainer from './WidgetContainer.vue'

const props = defineProps({
  widgets: {
    type: Array,
    required: true
  },
  layout: {
    type: String,
    default: 'grid',
    validator: (value) => ['grid', 'list', 'compact'].includes(value)
  },
  isEditing: {
    type: Boolean,
    default: false
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits([
  'update:widgets',
  'addWidget',
  'finishEditing',
  'refreshWidget',
  'widgetSettings',
  'widgetFullscreen',
  'widgetViewDetails'
])

const dashboardStore = useDashboardStore()

// Local state for drag operations
const localWidgets = ref([...props.widgets])

// Watch for external widget changes
watch(() => props.widgets, (newWidgets) => {
  localWidgets.value = [...newWidgets]
}, { deep: true })

// Computed classes based on layout
const gridClass = computed(() => {
  return {
    'widget-grid': true,
    'widget-grid--grid': props.layout === 'grid',
    'widget-grid--list': props.layout === 'list',
    'widget-grid--compact': props.layout === 'compact'
  }
})

const itemClass = computed(() => {
  return {
    'widget-grid-item': true,
    'widget-grid-item--grid': props.layout === 'grid',
    'widget-grid-item--list': props.layout === 'list',
    'widget-grid-item--compact': props.layout === 'compact'
  }
})

// Widget component mapping
const widgetComponents = {
  // Core widgets - lazy loaded
  qr_scanner: defineAsyncComponent(() =>
    import('@/components/QRCodeScanner.vue')
  ),
  my_kpis: defineAsyncComponent(() =>
    import('@/components/DashboardOverview.vue')
  ),
  data_entry_shortcuts: defineAsyncComponent(() =>
    import('./widgets/DataEntryShortcuts.vue').catch(() => ({
      template: '<div class="text-center pa-4"><v-icon>mdi-form-select</v-icon><p class="text-grey mt-2">Data Entry Shortcuts</p></div>'
    }))
  ),
  recent_entries: defineAsyncComponent(() =>
    import('./widgets/RecentEntries.vue').catch(() => ({
      template: '<div class="text-center pa-4"><v-icon>mdi-history</v-icon><p class="text-grey mt-2">Recent Entries</p></div>'
    }))
  ),
  client_overview: defineAsyncComponent(() =>
    import('./widgets/ClientOverview.vue').catch(() => ({
      template: '<div class="text-center pa-4"><v-icon>mdi-domain</v-icon><p class="text-grey mt-2">Client Overview</p></div>'
    }))
  ),
  team_kpis: defineAsyncComponent(() =>
    import('./widgets/TeamKPIs.vue').catch(() => ({
      template: '<div class="text-center pa-4"><v-icon>mdi-account-group</v-icon><p class="text-grey mt-2">Team KPIs</p></div>'
    }))
  ),
  efficiency_trends: defineAsyncComponent(() =>
    import('./widgets/EfficiencyTrends.vue').catch(() => ({
      template: '<div class="text-center pa-4"><v-icon>mdi-trending-up</v-icon><p class="text-grey mt-2">Efficiency Trends</p></div>'
    }))
  ),
  attendance_summary: defineAsyncComponent(() =>
    import('@/components/AttendanceKPIs.vue')
  ),
  all_kpis_grid: defineAsyncComponent(() =>
    import('@/components/DashboardOverview.vue')
  ),
  predictions: defineAsyncComponent(() =>
    import('./widgets/Predictions.vue').catch(() => ({
      template: '<div class="text-center pa-4"><v-icon>mdi-crystal-ball</v-icon><p class="text-grey mt-2">AI Predictions</p></div>'
    }))
  ),
  analytics_deep_dive: defineAsyncComponent(() =>
    import('./widgets/AnalyticsDeepDive.vue').catch(() => ({
      template: '<div class="text-center pa-4"><v-icon>mdi-chart-areaspline</v-icon><p class="text-grey mt-2">Analytics Deep Dive</p></div>'
    }))
  ),
  reports: defineAsyncComponent(() =>
    import('./widgets/Reports.vue').catch(() => ({
      template: '<div class="text-center pa-4"><v-icon>mdi-file-document-outline</v-icon><p class="text-grey mt-2">Reports</p></div>'
    }))
  ),
  system_health: defineAsyncComponent(() =>
    import('./widgets/SystemHealth.vue').catch(() => ({
      template: '<div class="text-center pa-4"><v-icon>mdi-server</v-icon><p class="text-grey mt-2">System Health</p></div>'
    }))
  ),
  user_stats: defineAsyncComponent(() =>
    import('./widgets/UserStats.vue').catch(() => ({
      template: '<div class="text-center pa-4"><v-icon>mdi-account-cog</v-icon><p class="text-grey mt-2">User Stats</p></div>'
    }))
  ),
  audit_log: defineAsyncComponent(() =>
    import('./widgets/AuditLog.vue').catch(() => ({
      template: '<div class="text-center pa-4"><v-icon>mdi-clipboard-text-clock</v-icon><p class="text-grey mt-2">Audit Log</p></div>'
    }))
  )
}

// Fallback component for unknown widgets
const FallbackWidget = {
  template: `
    <div class="text-center py-8">
      <v-icon size="48" color="grey-lighten-1">mdi-puzzle-outline</v-icon>
      <p class="text-grey mt-2">Widget not found</p>
    </div>
  `
}

// Methods
const getWidgetComponent = (widgetKey) => {
  return widgetComponents[widgetKey] || FallbackWidget
}

const getWidgetProps = (widget) => {
  return {
    widgetKey: widget.widget_key,
    config: widget.custom_config || {},
    ...widget.custom_config
  }
}

const removeWidget = (widgetKey) => {
  dashboardStore.removeWidget(widgetKey)
}

const hideWidget = (widgetKey) => {
  dashboardStore.toggleWidgetVisibility(widgetKey)
}

const onDragEnd = () => {
  // Update order in store
  localWidgets.value.forEach((widget, index) => {
    const storeWidget = dashboardStore.widgets.find(
      w => w.widget_key === widget.widget_key
    )
    if (storeWidget) {
      storeWidget.widget_order = index + 1
    }
  })
  dashboardStore.saveToLocalStorage?.()
  emit('update:widgets', localWidgets.value)
}
</script>

<style scoped>
.widget-grid-wrapper {
  position: relative;
  min-height: 200px;
}

.widget-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}

/* Grid Layout */
.widget-grid--grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 16px;
}

.widget-grid-item--grid {
  min-height: 300px;
}

/* List Layout */
.widget-grid--list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.widget-grid-item--list {
  width: 100%;
}

/* Compact Layout */
.widget-grid--compact {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 12px;
}

.widget-grid-item--compact {
  min-height: 180px;
}

/* Drag states */
.widget-ghost {
  opacity: 0.5;
  background: rgb(var(--v-theme-primary-lighten-4));
  border-radius: 8px;
}

.widget-dragging {
  opacity: 0.9;
  transform: rotate(2deg);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
}

/* Empty state */
.empty-state {
  background: rgba(0, 0, 0, 0.02);
  border-radius: 16px;
  border: 2px dashed rgba(0, 0, 0, 0.1);
}

/* Dark mode */
.v-theme--dark .empty-state {
  background: rgba(255, 255, 255, 0.02);
  border-color: rgba(255, 255, 255, 0.1);
}

/* Responsive adjustments */
@media (max-width: 600px) {
  .widget-grid--grid {
    grid-template-columns: 1fr;
  }

  .widget-grid--compact {
    grid-template-columns: 1fr;
  }

  .widget-grid-item--grid,
  .widget-grid-item--compact {
    min-height: 250px;
  }
}

@media (min-width: 601px) and (max-width: 960px) {
  .widget-grid--grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .widget-grid--compact {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (min-width: 1920px) {
  .widget-grid--grid {
    grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
  }

  .widget-grid--compact {
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  }
}
</style>
