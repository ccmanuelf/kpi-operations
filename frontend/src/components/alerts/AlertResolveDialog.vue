<template>
  <div v-if="modelValue" class="dialog-overlay" @click.self="$emit('close')">
    <div class="dialog">
      <h3>{{ t('alerts.resolveAlert') }}</h3>
      <p>{{ alert?.title }}</p>
      <textarea
        :value="notes"
        @input="$emit('update:notes', $event.target.value)"
        :placeholder="t('alerts.resolvePlaceholder')"
        rows="4"
      ></textarea>
      <div class="dialog-actions">
        <button @click="$emit('close')" class="btn-cancel">{{ t('common.cancel') }}</button>
        <button @click="$emit('confirm')" class="btn-resolve" :disabled="!notes.trim()">
          {{ t('alerts.resolve') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  alert: {
    type: Object,
    default: null
  },
  notes: {
    type: String,
    default: ''
  }
})

defineEmits(['close', 'confirm', 'update:notes'])
</script>

<style scoped>
.dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.dialog {
  background: var(--color-surface);
  padding: 1.5rem;
  border-radius: 8px;
  width: 100%;
  max-width: 500px;
}

.dialog h3 {
  margin-bottom: 0.5rem;
}

.dialog p {
  margin-bottom: 1rem;
  color: var(--color-text-muted);
}

.dialog textarea {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  resize: vertical;
  margin-bottom: 1rem;
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
}

.btn-cancel {
  padding: 0.5rem 1rem;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  cursor: pointer;
}

.btn-resolve {
  padding: 0.5rem 1rem;
  background: #16a34a;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.btn-resolve:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
