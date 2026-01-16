<template>
  <v-dialog v-model="isOpen" max-width="600" scrollable persistent>
    <v-card>
      <v-card-title class="d-flex align-center pa-4 bg-primary">
        <v-icon class="mr-2">mdi-view-dashboard-edit</v-icon>
        <span class="text-h5">Customize Dashboard</span>
        <v-spacer></v-spacer>
        <v-btn icon variant="text" @click="cancel">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>

      <v-card-text class="pa-0">
        <!-- Layout Selection -->
        <div class="pa-4 border-b">
          <div class="text-subtitle-2 mb-3">Layout Style</div>
          <v-btn-toggle
            v-model="localLayout"
            mandatory
            color="primary"
            variant="outlined"
            divided
          >
            <v-btn value="grid">
              <v-icon start>mdi-view-grid</v-icon>
              Grid
            </v-btn>
            <v-btn value="list">
              <v-icon start>mdi-view-list</v-icon>
              List
            </v-btn>
            <v-btn value="compact">
              <v-icon start>mdi-view-compact</v-icon>
              Compact
            </v-btn>
          </v-btn-toggle>
        </div>

        <!-- Active Widgets Section -->
        <div class="pa-4 border-b">
          <div class="d-flex align-center mb-3">
            <div class="text-subtitle-2">Active Widgets</div>
            <v-spacer />
            <v-chip size="small" color="primary" variant="tonal">
              {{ localVisibleWidgets.length }} active
            </v-chip>
          </div>

          <div v-if="localVisibleWidgets.length === 0" class="text-center py-6">
            <v-icon size="48" color="grey-lighten-1">mdi-widgets-outline</v-icon>
            <p class="text-grey mt-2">No widgets added. Add widgets from below.</p>
          </div>

          <draggable
            v-else
            v-model="localVisibleWidgets"
            item-key="widget_key"
            handle=".drag-handle"
            ghost-class="widget-ghost"
            class="widget-list"
            @end="onDragEnd"
          >
            <template #item="{ element, index }">
              <div class="widget-item d-flex align-center pa-3 mb-2 rounded">
                <v-icon class="drag-handle mr-3 cursor-move" color="grey">mdi-drag</v-icon>
                <v-icon :icon="getWidgetIcon(element.widget_key)" class="mr-3" color="primary" />
                <div class="flex-grow-1">
                  <div class="text-body-2 font-weight-medium">{{ element.widget_name }}</div>
                  <div class="text-caption text-grey">
                    {{ getWidgetDescription(element.widget_key) }}
                  </div>
                </div>
                <v-btn
                  icon
                  size="small"
                  variant="text"
                  color="grey"
                  @click="hideWidget(element.widget_key)"
                >
                  <v-icon>mdi-eye-off</v-icon>
                  <v-tooltip activator="parent" location="top">Hide Widget</v-tooltip>
                </v-btn>
              </div>
            </template>
          </draggable>
        </div>

        <!-- Available Widgets Section -->
        <div class="pa-4">
          <div class="d-flex align-center mb-3">
            <div class="text-subtitle-2">Available Widgets</div>
            <v-spacer />
            <v-chip size="small" color="grey" variant="tonal">
              {{ availableToAdd.length }} available
            </v-chip>
          </div>

          <div v-if="availableToAdd.length === 0" class="text-center py-4">
            <v-icon size="32" color="grey-lighten-1">mdi-check-circle</v-icon>
            <p class="text-grey text-caption mt-2">All available widgets are added</p>
          </div>

          <v-list v-else density="compact" class="pa-0">
            <v-list-item
              v-for="widget in availableToAdd"
              :key="widget.widget_key"
              class="widget-item mb-2 rounded px-3"
              @click="addWidget(widget.widget_key)"
            >
              <template v-slot:prepend>
                <v-icon :icon="widget.icon" color="grey-darken-1" class="mr-3" />
              </template>

              <v-list-item-title class="text-body-2">
                {{ widget.name }}
              </v-list-item-title>
              <v-list-item-subtitle class="text-caption">
                {{ widget.description }}
              </v-list-item-subtitle>

              <template v-slot:append>
                <v-btn
                  icon
                  size="small"
                  variant="text"
                  color="primary"
                >
                  <v-icon>mdi-plus</v-icon>
                  <v-tooltip activator="parent" location="top">Add Widget</v-tooltip>
                </v-btn>
              </template>
            </v-list-item>
          </v-list>
        </div>
      </v-card-text>

      <v-divider></v-divider>

      <v-card-actions class="pa-4">
        <v-btn
          variant="text"
          color="warning"
          prepend-icon="mdi-restore"
          @click="confirmReset"
        >
          Reset to Defaults
        </v-btn>
        <v-spacer />
        <v-btn
          variant="text"
          @click="cancel"
        >
          Cancel
        </v-btn>
        <v-btn
          color="primary"
          variant="flat"
          :loading="saving"
          @click="save"
        >
          Save Changes
        </v-btn>
      </v-card-actions>
    </v-card>

    <!-- Reset Confirmation Dialog -->
    <v-dialog v-model="showResetDialog" max-width="400">
      <v-card>
        <v-card-title class="text-h6">Reset Dashboard?</v-card-title>
        <v-card-text>
          This will reset your dashboard to the default layout for your role ({{ userRole }}).
          All customizations will be lost.
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="showResetDialog = false">Cancel</v-btn>
          <v-btn color="warning" variant="flat" @click="resetToDefaults">Reset</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-dialog>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import draggable from 'vuedraggable'
import { useDashboardStore } from '@/stores/dashboardStore'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue', 'saved'])

const dashboardStore = useDashboardStore()

// Local state
const isOpen = ref(props.modelValue)
const localLayout = ref('grid')
const localWidgets = ref([])
const saving = ref(false)
const showResetDialog = ref(false)

// Computed
const userRole = computed(() => dashboardStore.userRole)

const localVisibleWidgets = computed({
  get() {
    return localWidgets.value
      .filter(w => w.is_visible)
      .sort((a, b) => a.widget_order - b.widget_order)
  },
  set(value) {
    // Update order based on new arrangement
    value.forEach((widget, index) => {
      const w = localWidgets.value.find(x => x.widget_key === widget.widget_key)
      if (w) {
        w.widget_order = index + 1
      }
    })
  }
})

const availableToAdd = computed(() => {
  const activeKeys = new Set(
    localWidgets.value.filter(w => w.is_visible).map(w => w.widget_key)
  )
  return dashboardStore.availableWidgets.filter(w => !activeKeys.has(w.widget_key))
})

// Methods
const getWidgetIcon = (widgetKey) => {
  return dashboardStore.ALL_WIDGETS[widgetKey]?.icon || 'mdi-widgets'
}

const getWidgetDescription = (widgetKey) => {
  return dashboardStore.ALL_WIDGETS[widgetKey]?.description || ''
}

const hideWidget = (widgetKey) => {
  const widget = localWidgets.value.find(w => w.widget_key === widgetKey)
  if (widget) {
    widget.is_visible = false
  }
}

const addWidget = (widgetKey) => {
  const existing = localWidgets.value.find(w => w.widget_key === widgetKey)
  if (existing) {
    existing.is_visible = true
    existing.widget_order = localVisibleWidgets.value.length + 1
  } else {
    const widgetInfo = dashboardStore.ALL_WIDGETS[widgetKey]
    if (widgetInfo) {
      localWidgets.value.push({
        widget_key: widgetKey,
        widget_name: widgetInfo.name,
        widget_order: localVisibleWidgets.value.length + 1,
        is_visible: true,
        custom_config: {}
      })
    }
  }
}

const onDragEnd = () => {
  // Order is already updated by the computed setter
}

const confirmReset = () => {
  showResetDialog.value = true
}

const resetToDefaults = async () => {
  showResetDialog.value = false
  await dashboardStore.resetToDefaults()
  initializeLocalState()
}

const initializeLocalState = () => {
  localLayout.value = dashboardStore.layout
  localWidgets.value = JSON.parse(JSON.stringify(dashboardStore.widgets))
}

const save = async () => {
  saving.value = true
  try {
    // Apply local state to store
    dashboardStore.setLayout(localLayout.value)

    // Update widgets in store
    dashboardStore.widgets.splice(0, dashboardStore.widgets.length, ...localWidgets.value)

    // Save to API
    await dashboardStore.saveToAPI()

    emit('saved')
    close()
  } catch (error) {
    console.error('Failed to save dashboard preferences:', error)
  } finally {
    saving.value = false
  }
}

const cancel = () => {
  // Revert changes
  initializeLocalState()
  close()
}

const close = () => {
  isOpen.value = false
}

// Watch for external changes
watch(() => props.modelValue, (newValue) => {
  isOpen.value = newValue
  if (newValue) {
    initializeLocalState()
  }
})

// Emit changes
watch(isOpen, (newValue) => {
  emit('update:modelValue', newValue)
})

// Initialize on mount
onMounted(() => {
  initializeLocalState()
})
</script>

<style scoped>
.border-b {
  border-bottom: 1px solid rgba(0, 0, 0, 0.12);
}

.widget-item {
  border: 1px solid rgba(0, 0, 0, 0.12);
  background: rgba(0, 0, 0, 0.02);
  transition: all 0.2s ease;
}

.widget-item:hover {
  background: rgba(0, 0, 0, 0.04);
  border-color: rgba(0, 0, 0, 0.2);
}

.drag-handle {
  cursor: move;
}

.cursor-move {
  cursor: move;
}

.widget-ghost {
  opacity: 0.5;
  background: rgb(var(--v-theme-primary));
  border-radius: 8px;
}

.widget-list {
  min-height: 50px;
}

/* Dark mode support */
.v-theme--dark .widget-item {
  background: rgba(255, 255, 255, 0.02);
  border-color: rgba(255, 255, 255, 0.12);
}

.v-theme--dark .widget-item:hover {
  background: rgba(255, 255, 255, 0.05);
  border-color: rgba(255, 255, 255, 0.2);
}

.v-theme--dark .border-b {
  border-bottom-color: rgba(255, 255, 255, 0.12);
}
</style>
