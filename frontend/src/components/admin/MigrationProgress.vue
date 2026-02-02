<template>
  <v-card variant="outlined" class="pa-4">
    <!-- Progress Circle -->
    <div class="text-center mb-6">
      <v-progress-circular
        :model-value="progress"
        :size="140"
        :width="14"
        :color="statusColor"
      >
        <div class="text-center">
          <div class="text-h4 font-weight-bold">{{ progress }}%</div>
          <div class="text-caption text-medium-emphasis">{{ statusLabel }}</div>
        </div>
      </v-progress-circular>
    </div>

    <!-- Status Alert -->
    <v-alert :type="alertType" variant="tonal" class="mb-4">
      <v-alert-title class="d-flex align-center">
        <v-icon :icon="statusIcon" class="mr-2" />
        {{ statusTitle }}
      </v-alert-title>
      <p v-if="status?.current_step" class="mb-0">
        {{ status.current_step }}
      </p>
    </v-alert>

    <!-- Progress Details -->
    <v-list density="compact" v-if="status">
      <v-list-item v-if="status.current_table">
        <template v-slot:prepend>
          <v-icon>mdi-table</v-icon>
        </template>
        <v-list-item-title>Current Table</v-list-item-title>
        <v-list-item-subtitle>{{ status.current_table }}</v-list-item-subtitle>
      </v-list-item>

      <v-list-item v-if="status.total_tables > 0">
        <template v-slot:prepend>
          <v-icon>mdi-counter</v-icon>
        </template>
        <v-list-item-title>Tables Progress</v-list-item-title>
        <v-list-item-subtitle>
          {{ status.tables_migrated }} / {{ status.total_tables }} tables
        </v-list-item-subtitle>
      </v-list-item>
    </v-list>

    <!-- Error Message -->
    <v-alert
      v-if="status?.error_message"
      type="error"
      variant="outlined"
      class="mt-4"
    >
      <v-alert-title>Migration Error</v-alert-title>
      <p class="mb-0 text-body-2">{{ status.error_message }}</p>
    </v-alert>

    <!-- Actions -->
    <div v-if="isComplete" class="text-center mt-6">
      <v-btn
        v-if="status?.status === 'completed'"
        color="success"
        @click="$emit('dismiss')"
      >
        <v-icon start>mdi-check</v-icon>
        Done
      </v-btn>
      <v-btn
        v-else-if="status?.status === 'failed'"
        color="primary"
        @click="$emit('dismiss')"
      >
        <v-icon start>mdi-refresh</v-icon>
        Try Again
      </v-btn>
    </div>

    <!-- Linear Progress for in_progress -->
    <v-progress-linear
      v-if="status?.status === 'in_progress'"
      :model-value="progress"
      :color="statusColor"
      height="8"
      class="mt-4"
      rounded
    />
  </v-card>
</template>

<script setup>
import { computed } from 'vue'

// Props
const props = defineProps({
  status: {
    type: Object,
    default: null
  },
  progress: {
    type: Number,
    default: 0
  }
})

// Emits
defineEmits(['dismiss'])

// Computed
const statusColor = computed(() => {
  switch (props.status?.status) {
    case 'completed': return 'success'
    case 'failed': return 'error'
    case 'in_progress': return 'primary'
    default: return 'grey'
  }
})

const alertType = computed(() => {
  switch (props.status?.status) {
    case 'completed': return 'success'
    case 'failed': return 'error'
    case 'in_progress': return 'info'
    default: return 'info'
  }
})

const statusIcon = computed(() => {
  switch (props.status?.status) {
    case 'completed': return 'mdi-check-circle'
    case 'failed': return 'mdi-alert-circle'
    case 'in_progress': return 'mdi-loading mdi-spin'
    default: return 'mdi-clock-outline'
  }
})

const statusTitle = computed(() => {
  switch (props.status?.status) {
    case 'completed': return 'Migration Complete'
    case 'failed': return 'Migration Failed'
    case 'in_progress': return 'Migration In Progress'
    default: return 'Migration Status'
  }
})

const statusLabel = computed(() => {
  switch (props.status?.status) {
    case 'completed': return 'Complete'
    case 'failed': return 'Failed'
    case 'in_progress': return 'In Progress'
    default: return 'Idle'
  }
})

const isComplete = computed(() => {
  return props.status?.status === 'completed' || props.status?.status === 'failed'
})
</script>

<style scoped>
.mdi-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
