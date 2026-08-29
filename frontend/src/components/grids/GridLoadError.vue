<template>
  <v-alert
    v-if="message !== null"
    type="error" variant="tonal" density="compact" class="mb-3"
    role="alert"
  >
    <div class="d-flex align-center ga-3">
      <div class="flex-grow-1">
        <div class="font-weight-medium">{{ t('grids.loadFailed') }}</div>
        <!-- The backend's own reason, when it gave one. A failed load with no
             detail still shows the heading: an unexplained empty grid is the
             thing this exists to prevent. -->
        <div v-if="message" class="text-body-2">{{ message }}</div>
      </div>
      <v-btn size="small" variant="text" :loading="loading" @click="$emit('retry')">
        {{ t('grids.loadFailedRetry') }}
      </v-btn>
    </div>
  </v-alert>
</template>

<script setup lang="ts">
/**
 * Explains an empty grid that is empty because the load failed.
 *
 * `null` means the load is fine and nothing renders; a string — including the
 * empty string — means it failed. That distinction is the whole point: the
 * store resolves `{success: false}` without throwing and does not always carry
 * a message, so "no error text" must not be mistaken for "no error".
 */
import { useI18n } from 'vue-i18n'

defineProps<{
  /** null when healthy; the backend's reason, or '' when it gave none. */
  message: string | null
  loading?: boolean
}>()

defineEmits<{ retry: [] }>()

const { t } = useI18n()
</script>
