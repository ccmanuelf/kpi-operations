<template>
  <v-dialog v-model="dialogVisible" max-width="650" persistent>
    <v-card>
      <v-card-title class="d-flex align-center bg-primary">
        <v-icon color="white" class="mr-2">mdi-clipboard-check</v-icon>
        <span class="text-white">{{ title }}</span>
      </v-card-title>

      <v-card-text class="pt-4">
        <v-alert type="info" variant="tonal" class="mb-4">
          <div class="d-flex align-center">
            <v-icon class="mr-2">mdi-information</v-icon>
            <span>{{ subtitle }}</span>
          </div>
        </v-alert>

        <v-table density="comfortable" class="read-back-table">
          <thead>
            <tr>
              <th class="text-left font-weight-bold">{{ $t('readBack.field') }}</th>
              <th class="text-left font-weight-bold">{{ $t('readBack.value') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(item, index) in displayData" :key="index">
              <td class="field-label">{{ item.label }}</td>
              <td class="field-value" :class="getValueClass(item)">
                <template v-if="item.type === 'boolean'">
                  <v-icon :color="item.value ? 'success' : 'error'" size="small">
                    {{ item.value ? 'mdi-check-circle' : 'mdi-close-circle' }}
                  </v-icon>
                  {{ item.value ? $t('common.yes') : $t('common.no') }}
                </template>
                <template v-else-if="item.type === 'currency'">
                  {{ formatCurrency(item.value) }}
                </template>
                <template v-else-if="item.type === 'number'">
                  {{ formatNumber(item.value) }}
                </template>
                <template v-else-if="item.type === 'date'">
                  {{ formatDate(item.value) }}
                </template>
                <template v-else-if="item.type === 'datetime'">
                  {{ formatDateTime(item.value) }}
                </template>
                <template v-else-if="item.type === 'percentage'">
                  {{ formatPercentage(item.value) }}
                </template>
                <template v-else>
                  {{ item.displayValue || item.value || '-' }}
                </template>
              </td>
            </tr>
          </tbody>
        </v-table>

        <v-alert
          v-if="warningMessage"
          type="warning"
          variant="tonal"
          class="mt-4"
          density="compact"
        >
          {{ warningMessage }}
        </v-alert>
      </v-card-text>

      <v-divider />

      <v-card-actions class="pa-4">
        <v-btn
          color="error"
          variant="text"
          @click="handleCancel"
          :disabled="loading"
        >
          <v-icon left>mdi-close</v-icon>
          {{ $t('common.cancel') }}
        </v-btn>
        <v-spacer />
        <v-btn
          color="primary"
          variant="elevated"
          @click="handleConfirm"
          :loading="loading"
        >
          <v-icon left>mdi-check</v-icon>
          {{ $t('readBack.confirmAndSave') }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { format } from 'date-fns'

const { t } = useI18n()

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  title: {
    type: String,
    default: 'Confirm Entry - Read Back'
  },
  subtitle: {
    type: String,
    default: 'Please verify the following data before saving:'
  },
  data: {
    type: Object,
    default: () => ({})
  },
  fieldConfig: {
    type: Array,
    default: () => []
  },
  warningMessage: {
    type: String,
    default: ''
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue', 'confirm', 'cancel'])

const dialogVisible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

/**
 * Transform the raw data into display format using fieldConfig
 * fieldConfig format:
 * [
 *   { key: 'field_name', label: 'Display Label', type: 'text|number|date|datetime|boolean|currency|percentage', displayValue?: 'optional transformed value' },
 *   ...
 * ]
 */
const displayData = computed(() => {
  if (props.fieldConfig.length > 0) {
    return props.fieldConfig
      .filter(config => config.key in props.data)
      .map(config => ({
        label: config.label,
        value: props.data[config.key],
        displayValue: config.displayValue,
        type: config.type || 'text',
        highlight: config.highlight || false
      }))
  }

  // Fallback: auto-generate from data keys
  return Object.entries(props.data)
    .filter(([key]) => !key.startsWith('_'))
    .map(([key, value]) => ({
      label: formatLabel(key),
      value: value,
      type: detectType(value)
    }))
})

const formatLabel = (key) => {
  return key
    .replace(/_/g, ' ')
    .replace(/([A-Z])/g, ' $1')
    .replace(/\b\w/g, (char) => char.toUpperCase())
    .trim()
}

const detectType = (value) => {
  if (typeof value === 'boolean') return 'boolean'
  if (typeof value === 'number') return 'number'
  if (value instanceof Date) return 'datetime'
  if (typeof value === 'string') {
    if (/^\d{4}-\d{2}-\d{2}T/.test(value)) return 'datetime'
    if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return 'date'
  }
  return 'text'
}

const formatNumber = (value) => {
  if (value === null || value === undefined) return '-'
  return typeof value === 'number' ? value.toLocaleString() : value
}

const formatCurrency = (value) => {
  if (value === null || value === undefined) return '-'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD'
  }).format(value)
}

const formatPercentage = (value) => {
  if (value === null || value === undefined) return '-'
  return `${parseFloat(value).toFixed(2)}%`
}

const formatDate = (value) => {
  if (!value) return '-'
  try {
    return format(new Date(value), 'MMM dd, yyyy')
  } catch {
    return value
  }
}

const formatDateTime = (value) => {
  if (!value) return '-'
  try {
    return format(new Date(value), 'MMM dd, yyyy HH:mm')
  } catch {
    return value
  }
}

const getValueClass = (item) => {
  const classes = []
  if (item.highlight) classes.push('highlighted-value')
  if (item.type === 'boolean' && item.value) classes.push('text-success')
  if (item.type === 'boolean' && !item.value) classes.push('text-error')
  return classes.join(' ')
}

const handleConfirm = () => {
  emit('confirm', props.data)
}

const handleCancel = () => {
  emit('cancel')
  dialogVisible.value = false
}
</script>

<style scoped>
.read-back-table {
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 8px;
}

.read-back-table th {
  background-color: rgba(0, 0, 0, 0.04);
}

.field-label {
  font-weight: 500;
  color: rgba(0, 0, 0, 0.7);
  width: 40%;
}

.field-value {
  font-weight: 600;
}

.highlighted-value {
  background-color: rgba(25, 118, 210, 0.08);
}
</style>
