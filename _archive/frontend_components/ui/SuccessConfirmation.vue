<template>
  <v-dialog
    :model-value="modelValue"
    max-width="400"
    :persistent="persistent"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <v-card class="success-confirmation">
      <div class="success-confirmation__icon-wrapper">
        <v-icon
          :color="iconColor"
          :size="64"
          class="success-confirmation__icon"
        >
          {{ icon }}
        </v-icon>
      </div>

      <v-card-title class="success-confirmation__title text-center">
        {{ title }}
      </v-card-title>

      <v-card-text class="success-confirmation__message text-center">
        {{ message }}
        <div v-if="details" class="success-confirmation__details mt-3">
          <slot name="details">
            <div
              v-for="(value, key) in details"
              :key="key"
              class="success-confirmation__detail-row"
            >
              <span class="success-confirmation__detail-label">{{ formatLabel(key) }}:</span>
              <span class="success-confirmation__detail-value">{{ value }}</span>
            </div>
          </slot>
        </div>
      </v-card-text>

      <v-card-actions class="success-confirmation__actions justify-center pb-4">
        <v-btn
          v-if="secondaryAction"
          variant="outlined"
          @click="$emit('secondary')"
        >
          {{ secondaryAction }}
        </v-btn>
        <v-btn
          :color="buttonColor"
          variant="flat"
          @click="handleClose"
          :loading="loading"
        >
          {{ actionText }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { computed, watch } from 'vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  variant: {
    type: String,
    default: 'success',
    validator: (v) => ['success', 'info', 'warning'].includes(v)
  },
  title: {
    type: String,
    default: 'Success!'
  },
  message: {
    type: String,
    default: 'Operation completed successfully.'
  },
  details: {
    type: Object,
    default: null
  },
  actionText: {
    type: String,
    default: 'Done'
  },
  secondaryAction: {
    type: String,
    default: ''
  },
  autoDismiss: {
    type: Number,
    default: 0 // 0 = no auto dismiss
  },
  persistent: {
    type: Boolean,
    default: false
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue', 'close', 'secondary'])

const variantConfig = {
  success: {
    icon: 'mdi-check-circle',
    color: 'success'
  },
  info: {
    icon: 'mdi-information',
    color: 'info'
  },
  warning: {
    icon: 'mdi-alert',
    color: 'warning'
  }
}

const icon = computed(() => variantConfig[props.variant].icon)
const iconColor = computed(() => variantConfig[props.variant].color)
const buttonColor = computed(() => variantConfig[props.variant].color)

const formatLabel = (key) => {
  return key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
}

const handleClose = () => {
  emit('update:modelValue', false)
  emit('close')
}

// Auto dismiss
watch(() => props.modelValue, (newValue) => {
  if (newValue && props.autoDismiss > 0) {
    setTimeout(() => {
      handleClose()
    }, props.autoDismiss)
  }
})
</script>

<style scoped>
.success-confirmation {
  overflow: hidden;
}

.success-confirmation__icon-wrapper {
  display: flex;
  justify-content: center;
  padding-top: var(--cds-spacing-07);
}

.success-confirmation__icon {
  animation: bounceIn 0.5s var(--cds-easing-entrance-expressive);
}

.success-confirmation__title {
  font-size: var(--cds-heading-04-font-size) !important;
  font-weight: var(--cds-heading-04-font-weight) !important;
  color: var(--cds-text-primary);
  padding-top: var(--cds-spacing-04) !important;
}

.success-confirmation__message {
  font-size: var(--cds-body-short-02-font-size);
  color: var(--cds-text-secondary);
}

.success-confirmation__details {
  background-color: var(--cds-layer-01);
  border-radius: var(--cds-border-radius-md);
  padding: var(--cds-spacing-04);
  text-align: left;
}

.success-confirmation__detail-row {
  display: flex;
  justify-content: space-between;
  padding: var(--cds-spacing-02) 0;
  border-bottom: 1px solid var(--cds-border-subtle-00);
}

.success-confirmation__detail-row:last-child {
  border-bottom: none;
}

.success-confirmation__detail-label {
  font-size: var(--cds-body-short-01-font-size);
  color: var(--cds-text-secondary);
}

.success-confirmation__detail-value {
  font-size: var(--cds-body-short-01-font-size);
  font-weight: 500;
  color: var(--cds-text-primary);
}

.success-confirmation__actions {
  gap: var(--cds-spacing-03);
}

@keyframes bounceIn {
  0% {
    opacity: 0;
    transform: scale(0.3);
  }
  50% {
    transform: scale(1.05);
  }
  70% {
    transform: scale(0.95);
  }
  100% {
    opacity: 1;
    transform: scale(1);
  }
}

/* Reduced motion */
@media (prefers-reduced-motion: reduce) {
  .success-confirmation__icon {
    animation: none;
  }
}
</style>
