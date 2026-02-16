<template>
  <div
    class="empty-state"
    :class="[`empty-state--${size}`, { 'empty-state--elevated': elevated }]"
    role="status"
    :aria-label="ariaLabel || title"
  >
    <v-icon
      :size="iconSize"
      :color="iconColor"
      class="empty-state__icon"
      aria-hidden="true"
    >
      {{ iconComputed }}
    </v-icon>

    <h3 class="empty-state__title">{{ title }}</h3>

    <p v-if="description" class="empty-state__description">
      {{ description }}
    </p>

    <div v-if="$slots.default" class="empty-state__actions">
      <slot></slot>
    </div>

    <v-btn
      v-else-if="actionText"
      :color="actionColor"
      :variant="actionVariant"
      :prepend-icon="actionIcon"
      @click="$emit('action')"
      class="empty-state__action-btn"
    >
      {{ actionText }}
    </v-btn>
  </div>
</template>

<script setup>
/**
 * EmptyState - Reusable empty/no-data placeholder component.
 *
 * Displays an icon, title, optional description, and optional action button
 * when a view or table has no data to show. Supports multiple visual variants
 * (no-data, no-results, error, empty-table, no-entries, no-filter-match)
 * and three sizes (small, medium, large).
 *
 * @prop {string} title - Heading text (default: 'No data found')
 * @prop {string} description - Explanatory subtext
 * @prop {string} icon - Override icon (auto-selected from variant if empty)
 * @prop {string} variant - Visual preset: default|no-data|no-results|error|empty-table|no-entries|no-filter-match
 * @prop {string} size - Component size: small|medium|large
 * @prop {string} actionText - If set, renders an action button
 * @prop {boolean} elevated - Adds background and border styling
 * @emits action - Fired when the action button is clicked
 * @slot default - Custom action content (replaces actionText button)
 */
import { computed } from 'vue'

const props = defineProps({
  // Content
  title: {
    type: String,
    default: 'No data found'
  },
  description: {
    type: String,
    default: ''
  },

  // Icon
  icon: {
    type: String,
    default: ''
  },
  iconColor: {
    type: String,
    default: 'grey-darken-1'
  },

  // Variant - determines icon and styling
  variant: {
    type: String,
    default: 'default',
    validator: (v) => ['default', 'no-data', 'no-results', 'error', 'empty-table', 'no-entries', 'no-filter-match'].includes(v)
  },

  // Size
  size: {
    type: String,
    default: 'medium',
    validator: (v) => ['small', 'medium', 'large'].includes(v)
  },

  // Action button
  actionText: {
    type: String,
    default: ''
  },
  actionIcon: {
    type: String,
    default: ''
  },
  actionColor: {
    type: String,
    default: 'primary'
  },
  actionVariant: {
    type: String,
    default: 'flat'
  },

  // Styling
  elevated: {
    type: Boolean,
    default: false
  },

  // Accessibility
  ariaLabel: {
    type: String,
    default: ''
  }
})

defineEmits(['action'])

const variantConfig = {
  'default': {
    icon: 'mdi-tray-alert',
  },
  'no-data': {
    icon: 'mdi-database-off-outline',
  },
  'no-results': {
    icon: 'mdi-magnify-close',
  },
  'error': {
    icon: 'mdi-alert-circle-outline',
  },
  'empty-table': {
    icon: 'mdi-table-off',
  },
  'no-entries': {
    icon: 'mdi-file-document-outline',
  },
  'no-filter-match': {
    icon: 'mdi-filter-off-outline',
  }
}

const iconComputed = computed(() => {
  if (props.icon) return props.icon
  return variantConfig[props.variant]?.icon || 'mdi-tray-alert'
})

const iconSize = computed(() => {
  const sizes = {
    small: 48,
    medium: 64,
    large: 80
  }
  return sizes[props.size]
})
</script>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: var(--cds-spacing-07);
  min-height: 200px;
}

.empty-state--small {
  padding: var(--cds-spacing-05);
  min-height: 120px;
}

.empty-state--large {
  padding: var(--cds-spacing-09);
  min-height: 300px;
}

.empty-state--elevated {
  background-color: var(--cds-layer-01);
  border-radius: var(--cds-border-radius-lg);
  border: 1px solid var(--cds-border-subtle-00);
}

.empty-state__icon {
  margin-bottom: var(--cds-spacing-05);
  opacity: 0.6;
}

.empty-state__title {
  font-size: var(--cds-heading-03-font-size);
  font-weight: var(--cds-heading-03-font-weight);
  line-height: var(--cds-heading-03-line-height);
  color: var(--cds-text-primary);
  margin: 0 0 var(--cds-spacing-03);
}

.empty-state--small .empty-state__title {
  font-size: var(--cds-heading-02-font-size);
}

.empty-state--large .empty-state__title {
  font-size: var(--cds-heading-04-font-size);
}

.empty-state__description {
  font-size: var(--cds-body-short-01-font-size);
  line-height: var(--cds-body-short-01-line-height);
  color: var(--cds-text-secondary);
  max-width: 400px;
  margin: 0 0 var(--cds-spacing-05);
}

.empty-state__actions {
  display: flex;
  gap: var(--cds-spacing-03);
  margin-top: var(--cds-spacing-03);
}

.empty-state__action-btn {
  margin-top: var(--cds-spacing-03);
}

/* Animation for appearance */
.empty-state {
  animation: fadeIn var(--cds-duration-moderate-02) var(--cds-easing-entrance-productive);
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Reduced motion support */
@media (prefers-reduced-motion: reduce) {
  .empty-state {
    animation: none;
  }
}
</style>
