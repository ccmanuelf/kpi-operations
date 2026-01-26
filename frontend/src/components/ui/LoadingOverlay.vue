<template>
  <Teleport to="body">
    <Transition name="fade">
      <div
        v-if="modelValue"
        class="loading-overlay"
        :class="{ 'loading-overlay--contained': contained }"
        role="status"
        aria-live="polite"
        :aria-label="text || 'Loading'"
      >
        <div class="loading-overlay__backdrop" @click.prevent></div>
        <div class="loading-overlay__content">
          <v-progress-circular
            :size="size"
            :width="width"
            :color="color"
            indeterminate
            aria-hidden="true"
          />
          <span v-if="text" class="loading-overlay__text">{{ text }}</span>
          <span v-if="subtext" class="loading-overlay__subtext">{{ subtext }}</span>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  text: {
    type: String,
    default: ''
  },
  subtext: {
    type: String,
    default: ''
  },
  size: {
    type: [Number, String],
    default: 64
  },
  width: {
    type: Number,
    default: 4
  },
  color: {
    type: String,
    default: 'primary'
  },
  contained: {
    type: Boolean,
    default: false
  }
})
</script>

<style scoped>
.loading-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
}

.loading-overlay--contained {
  position: absolute;
}

.loading-overlay__backdrop {
  position: absolute;
  inset: 0;
  background-color: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(2px);
}

[data-theme="dark"] .loading-overlay__backdrop,
.dark-theme .loading-overlay__backdrop {
  background-color: rgba(22, 22, 22, 0.85);
}

.loading-overlay__content {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--cds-spacing-04);
  padding: var(--cds-spacing-06);
  background: var(--cds-layer-02);
  border-radius: var(--cds-border-radius-lg);
  box-shadow: var(--cds-shadow-lg);
}

.loading-overlay__text {
  font-size: var(--cds-body-short-02-font-size);
  font-weight: 500;
  color: var(--cds-text-primary);
  text-align: center;
}

.loading-overlay__subtext {
  font-size: var(--cds-body-short-01-font-size);
  color: var(--cds-text-secondary);
  text-align: center;
}

/* Transition */
.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--cds-duration-moderate-01) var(--cds-easing-standard-productive);
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Reduced motion support */
@media (prefers-reduced-motion: reduce) {
  .fade-enter-active,
  .fade-leave-active {
    transition: none;
  }
}
</style>
