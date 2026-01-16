<template>
  <v-card
    class="widget-container"
    :class="{
      'editing': isEditing,
      'widget-compact': layout === 'compact',
      'widget-list': layout === 'list'
    }"
    :elevation="isEditing ? 4 : 2"
  >
    <v-card-title class="widget-header d-flex align-center py-2 px-4">
      <!-- Drag Handle (edit mode only) -->
      <v-icon
        v-if="isEditing"
        class="drag-handle mr-2"
        color="grey"
        size="20"
      >
        mdi-drag
      </v-icon>

      <!-- Widget Icon -->
      <v-icon
        :icon="widgetIcon"
        :color="isEditing ? 'grey' : 'primary'"
        size="20"
        class="mr-2"
      />

      <!-- Widget Title -->
      <span class="text-subtitle-1 font-weight-medium">{{ widget.widget_name }}</span>

      <v-spacer />

      <!-- Widget Menu (normal mode) -->
      <v-menu v-if="!isEditing && showMenu" location="bottom end">
        <template v-slot:activator="{ props: menuProps }">
          <v-btn
            icon
            size="small"
            variant="text"
            v-bind="menuProps"
          >
            <v-icon size="18">mdi-dots-vertical</v-icon>
          </v-btn>
        </template>
        <v-list density="compact">
          <v-list-item
            v-if="hasRefresh"
            prepend-icon="mdi-refresh"
            @click="$emit('refresh')"
          >
            <v-list-item-title>Refresh</v-list-item-title>
          </v-list-item>
          <v-list-item
            v-if="hasSettings"
            prepend-icon="mdi-cog"
            @click="$emit('settings')"
          >
            <v-list-item-title>Settings</v-list-item-title>
          </v-list-item>
          <v-list-item
            v-if="hasFullscreen"
            prepend-icon="mdi-fullscreen"
            @click="$emit('fullscreen')"
          >
            <v-list-item-title>Fullscreen</v-list-item-title>
          </v-list-item>
          <v-divider v-if="hasRefresh || hasSettings || hasFullscreen" class="my-1" />
          <v-list-item
            prepend-icon="mdi-eye-off"
            @click="$emit('hide')"
          >
            <v-list-item-title>Hide Widget</v-list-item-title>
          </v-list-item>
        </v-list>
      </v-menu>

      <!-- Remove Button (edit mode only) -->
      <v-btn
        v-if="isEditing"
        icon
        size="small"
        variant="text"
        color="error"
        @click="$emit('remove')"
      >
        <v-icon size="18">mdi-close</v-icon>
        <v-tooltip activator="parent" location="top">Remove Widget</v-tooltip>
      </v-btn>
    </v-card-title>

    <v-divider v-if="!isEditing" />

    <!-- Widget Content -->
    <v-card-text
      class="widget-content"
      :class="{
        'pa-4': layout !== 'compact',
        'pa-2': layout === 'compact',
        'content-preview': isEditing
      }"
    >
      <!-- Edit Mode Preview -->
      <div v-if="isEditing" class="edit-preview d-flex align-center justify-center">
        <div class="text-center">
          <v-icon :icon="widgetIcon" size="48" color="grey-lighten-1" />
          <div class="text-caption text-grey mt-2">{{ widget.widget_name }}</div>
        </div>
      </div>

      <!-- Normal Content Slot -->
      <template v-else>
        <slot>
          <!-- Default placeholder if no content -->
          <div class="text-center py-8">
            <v-icon size="48" color="grey-lighten-1">mdi-widgets-outline</v-icon>
            <p class="text-grey mt-2">Widget content goes here</p>
          </div>
        </slot>
      </template>
    </v-card-text>

    <!-- Optional Footer Slot -->
    <template v-if="$slots.footer && !isEditing">
      <v-divider />
      <v-card-actions class="px-4 py-2">
        <slot name="footer"></slot>
      </v-card-actions>
    </template>

    <!-- Edit Mode Overlay -->
    <div v-if="isEditing" class="edit-overlay" />
  </v-card>
</template>

<script setup>
import { computed } from 'vue'
import { useDashboardStore } from '@/stores/dashboardStore'

const props = defineProps({
  widget: {
    type: Object,
    required: true,
    validator: (value) => {
      return value.widget_key && value.widget_name
    }
  },
  isEditing: {
    type: Boolean,
    default: false
  },
  layout: {
    type: String,
    default: 'grid',
    validator: (value) => ['grid', 'list', 'compact'].includes(value)
  },
  showMenu: {
    type: Boolean,
    default: true
  },
  hasRefresh: {
    type: Boolean,
    default: true
  },
  hasSettings: {
    type: Boolean,
    default: false
  },
  hasFullscreen: {
    type: Boolean,
    default: false
  }
})

defineEmits(['remove', 'refresh', 'settings', 'fullscreen', 'hide'])

const dashboardStore = useDashboardStore()

const widgetIcon = computed(() => {
  return dashboardStore.ALL_WIDGETS[props.widget.widget_key]?.icon || 'mdi-widgets'
})
</script>

<style scoped>
.widget-container {
  position: relative;
  transition: all 0.3s ease;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.widget-container.editing {
  border: 2px dashed rgb(var(--v-theme-primary));
  cursor: move;
}

.widget-container.editing:hover {
  border-color: rgb(var(--v-theme-primary));
  box-shadow: 0 4px 20px rgba(var(--v-theme-primary), 0.3);
}

.widget-header {
  min-height: 48px;
  flex-shrink: 0;
}

.widget-content {
  flex: 1;
  overflow: auto;
}

.content-preview {
  min-height: 120px;
}

.drag-handle {
  cursor: move;
}

.edit-preview {
  min-height: 100px;
  background: rgba(0, 0, 0, 0.02);
  border-radius: 8px;
}

.edit-overlay {
  position: absolute;
  top: 48px;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(255, 255, 255, 0.6);
  pointer-events: none;
  z-index: 1;
}

/* List layout */
.widget-list {
  margin-bottom: 8px;
}

.widget-list .widget-content {
  max-height: 200px;
}

/* Compact layout */
.widget-compact .widget-header {
  min-height: 36px;
  padding: 4px 12px !important;
}

.widget-compact .widget-header .text-subtitle-1 {
  font-size: 0.875rem !important;
}

.widget-compact .widget-content {
  max-height: 150px;
}

/* Dark mode support */
.v-theme--dark .edit-preview {
  background: rgba(255, 255, 255, 0.02);
}

.v-theme--dark .edit-overlay {
  background: rgba(0, 0, 0, 0.4);
}
</style>
