<template>
  <Transition name="slide-fade">
    <div
      v-if="show"
      class="form-feedback"
      :class="[`form-feedback--${type}`]"
      role="alert"
      :aria-live="type === 'error' ? 'assertive' : 'polite'"
    >
      <v-icon
        :color="iconColor"
        size="20"
        class="form-feedback__icon"
        aria-hidden="true"
      >
        {{ icon }}
      </v-icon>
      <div class="form-feedback__content">
        <span class="form-feedback__message">{{ message }}</span>
        <span v-if="details" class="form-feedback__details">{{ details }}</span>
      </div>
      <v-btn
        v-if="dismissible"
        icon
        size="x-small"
        variant="text"
        :color="iconColor"
        @click="$emit('dismiss')"
        aria-label="Dismiss message"
        class="form-feedback__close"
      >
        <v-icon size="16">mdi-close</v-icon>
      </v-btn>
    </div>
  </Transition>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  show: {
    type: Boolean,
    default: true
  },
  type: {
    type: String,
    default: 'info',
    validator: (v) => ['success', 'error', 'warning', 'info'].includes(v)
  },
  message: {
    type: String,
    required: true
  },
  details: {
    type: String,
    default: ''
  },
  dismissible: {
    type: Boolean,
    default: false
  }
})

defineEmits(['dismiss'])

const typeConfig = {
  success: {
    icon: 'mdi-check-circle',
    color: 'success'
  },
  error: {
    icon: 'mdi-alert-circle',
    color: 'error'
  },
  warning: {
    icon: 'mdi-alert',
    color: 'warning'
  },
  info: {
    icon: 'mdi-information',
    color: 'info'
  }
}

const icon = computed(() => typeConfig[props.type].icon)
const iconColor = computed(() => typeConfig[props.type].color)
</script>

<style scoped>
.form-feedback {
  display: flex;
  align-items: flex-start;
  gap: var(--cds-spacing-03);
  padding: var(--cds-spacing-03) var(--cds-spacing-04);
  border-radius: var(--cds-border-radius-md);
  margin-top: var(--cds-spacing-02);
}

.form-feedback--success {
  background-color: var(--cds-green-10);
  border-left: 3px solid var(--cds-green-60);
}

.form-feedback--error {
  background-color: var(--cds-red-10);
  border-left: 3px solid var(--cds-red-60);
}

.form-feedback--warning {
  background-color: var(--cds-yellow-10);
  border-left: 3px solid var(--cds-yellow-30);
}

.form-feedback--info {
  background-color: var(--cds-blue-10);
  border-left: 3px solid var(--cds-blue-60);
}

.form-feedback__icon {
  flex-shrink: 0;
  margin-top: 2px;
}

.form-feedback__content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--cds-spacing-01);
}

.form-feedback__message {
  font-size: var(--cds-body-short-01-font-size);
  font-weight: 500;
  color: var(--cds-text-primary);
}

.form-feedback__details {
  font-size: var(--cds-caption-01-font-size);
  color: var(--cds-text-secondary);
}

.form-feedback__close {
  flex-shrink: 0;
  margin: -4px -8px -4px 0;
}

/* Transition */
.slide-fade-enter-active {
  transition: all var(--cds-duration-moderate-01) var(--cds-easing-entrance-productive);
}

.slide-fade-leave-active {
  transition: all var(--cds-duration-fast-02) var(--cds-easing-exit-productive);
}

.slide-fade-enter-from,
.slide-fade-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

/* Dark mode */
[data-theme="dark"] .form-feedback--success,
.dark-theme .form-feedback--success {
  background-color: rgba(36, 161, 72, 0.15);
}

[data-theme="dark"] .form-feedback--error,
.dark-theme .form-feedback--error {
  background-color: rgba(218, 30, 40, 0.15);
}

[data-theme="dark"] .form-feedback--warning,
.dark-theme .form-feedback--warning {
  background-color: rgba(241, 194, 27, 0.15);
}

[data-theme="dark"] .form-feedback--info,
.dark-theme .form-feedback--info {
  background-color: rgba(15, 98, 254, 0.15);
}

/* Reduced motion */
@media (prefers-reduced-motion: reduce) {
  .slide-fade-enter-active,
  .slide-fade-leave-active {
    transition: none;
  }
}
</style>
