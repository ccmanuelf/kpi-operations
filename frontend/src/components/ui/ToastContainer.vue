<template>
  <Teleport to="body">
    <div class="toast-container" aria-live="polite" aria-atomic="false">
      <TransitionGroup name="toast">
        <div
          v-for="toast in toasts"
          :key="toast.id"
          class="toast-wrapper"
        >
          <v-snackbar
            :model-value="toast.visible"
            :color="toast.color"
            location="bottom"
            :timeout="-1"
            multi-line
            class="toast-snackbar"
          >
            <div class="d-flex align-center">
              <v-icon class="mr-3" :aria-hidden="true">{{ toast.icon }}</v-icon>
              <span>{{ toast.message }}</span>
            </div>

            <template v-slot:actions>
              <v-btn
                v-if="toast.action"
                variant="text"
                @click="handleAction(toast)"
              >
                {{ toast.action }}
              </v-btn>
              <v-btn
                icon
                size="small"
                variant="text"
                @click="dismissToast(toast.id)"
                aria-label="Dismiss notification"
              >
                <v-icon>mdi-close</v-icon>
              </v-btn>
            </template>
          </v-snackbar>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<script setup>
import { useToast } from '@/composables/useToast'

const { toasts, dismissToast } = useToast()

const handleAction = (toast) => {
  if (toast.onAction) {
    toast.onAction()
  }
  dismissToast(toast.id)
}
</script>

<style scoped>
.toast-container {
  position: fixed;
  bottom: 16px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 10000;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 100%;
  width: 400px;
}

@media (max-width: 600px) {
  .toast-container {
    width: calc(100% - 32px);
    left: 16px;
    transform: none;
    bottom: 80px; /* Account for mobile navigation */
  }
}

.toast-wrapper {
  width: 100%;
}

/* Transition animations */
.toast-enter-active {
  transition: all 0.3s var(--cds-easing-entrance-productive);
}

.toast-leave-active {
  transition: all 0.2s var(--cds-easing-exit-productive);
}

.toast-enter-from {
  opacity: 0;
  transform: translateY(20px);
}

.toast-leave-to {
  opacity: 0;
  transform: translateX(100%);
}

.toast-move {
  transition: transform 0.3s var(--cds-easing-standard-productive);
}
</style>
