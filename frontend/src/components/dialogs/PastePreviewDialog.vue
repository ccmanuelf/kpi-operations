<template>
  <v-dialog
    :model-value="modelValue"
    @update:model-value="$emit('update:modelValue', $event)"
    max-width="900"
    persistent
  >
    <v-card>
      <v-card-title class="d-flex align-center bg-primary text-white">
        <v-icon class="mr-2">mdi-content-paste</v-icon>
        {{ $t('paste.previewTitle') }}
        <v-spacer />
        <v-chip v-if="validationResult" class="ml-2" :color="validationResult.isValid ? 'success' : 'warning'" variant="flat">
          {{ validationResult.totalValid }} {{ $t('paste.validRows') }}
          <span v-if="validationResult.totalInvalid > 0" class="ml-1">
            / {{ validationResult.totalInvalid }} {{ $t('paste.invalidRows') }}
          </span>
        </v-chip>
      </v-card-title>

      <v-card-text class="pa-4">
        <!-- Summary Info -->
        <v-alert v-if="parsedData" type="info" variant="tonal" density="compact" class="mb-4">
          <div class="d-flex align-center flex-wrap ga-3">
            <div>
              <v-icon class="mr-1">mdi-table-row</v-icon>
              {{ parsedData.totalRows }} {{ $t('paste.rowsDetected') }}
            </div>
            <div>
              <v-icon class="mr-1">mdi-table-column</v-icon>
              {{ parsedData.totalColumns }} {{ $t('paste.columnsDetected') }}
            </div>
            <div v-if="parsedData.hasHeaders">
              <v-icon class="mr-1">mdi-table-headers-eye</v-icon>
              {{ $t('paste.headersDetected') }}
            </div>
          </div>
        </v-alert>

        <!-- Column Mapping Section -->
        <div v-if="showColumnMapping && unmappedColumns.length > 0" class="mb-4">
          <v-alert type="warning" variant="tonal" density="compact">
            <div class="font-weight-medium mb-2">{{ $t('paste.unmappedColumns') }}:</div>
            <v-chip
              v-for="col in unmappedColumns"
              :key="col.index"
              size="small"
              class="mr-1 mb-1"
              color="warning"
            >
              {{ col.header }}
            </v-chip>
          </v-alert>
        </div>

        <!-- Validation Errors -->
        <v-expansion-panels v-if="validationResult?.invalidRows?.length > 0" class="mb-4">
          <v-expansion-panel>
            <v-expansion-panel-title>
              <div class="d-flex align-center">
                <v-icon color="error" class="mr-2">mdi-alert-circle</v-icon>
                {{ $t('paste.validationErrors') }} ({{ validationResult.invalidRows.length }})
              </div>
            </v-expansion-panel-title>
            <v-expansion-panel-text>
              <v-list density="compact">
                <v-list-item
                  v-for="(item, idx) in validationResult.invalidRows.slice(0, 10)"
                  :key="idx"
                >
                  <template v-slot:prepend>
                    <v-icon color="error" size="small">mdi-alert</v-icon>
                  </template>
                  <v-list-item-title class="text-body-2">
                    {{ $t('paste.row') }} {{ item.rowIndex + 1 }}:
                    <span class="text-error">{{ item.errors.join(', ') }}</span>
                  </v-list-item-title>
                </v-list-item>
                <v-list-item v-if="validationResult.invalidRows.length > 10">
                  <v-list-item-title class="text-body-2 text-grey">
                    ... {{ $t('paste.andMore', { count: validationResult.invalidRows.length - 10 }) }}
                  </v-list-item-title>
                </v-list-item>
              </v-list>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>

        <!-- Data Preview Table -->
        <div class="preview-table-container">
          <v-table density="compact" fixed-header height="350">
            <thead>
              <tr>
                <th class="text-center" style="width: 50px">#</th>
                <th
                  v-for="col in previewColumns"
                  :key="col.field"
                  :class="{ 'text-right': col.type === 'numericColumn' }"
                >
                  {{ col.headerName }}
                  <v-icon v-if="col.mapped" size="x-small" color="success" class="ml-1">mdi-check</v-icon>
                </th>
                <th class="text-center" style="width: 80px">{{ $t('common.status') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(row, idx) in previewRows"
                :key="idx"
                :class="{ 'bg-error-lighten-5': row._hasErrors }"
              >
                <td class="text-center text-caption">{{ idx + 1 }}</td>
                <td
                  v-for="col in previewColumns"
                  :key="col.field"
                  :class="{ 'text-right': col.type === 'numericColumn' }"
                >
                  <span :class="getCellClass(row, col)">
                    {{ formatCellValue(row[col.field], col) }}
                  </span>
                </td>
                <td class="text-center">
                  <v-icon v-if="row._hasErrors" color="error" size="small">mdi-alert-circle</v-icon>
                  <v-icon v-else color="success" size="small">mdi-check-circle</v-icon>
                </td>
              </tr>
              <tr v-if="previewRows.length === 0">
                <td :colspan="previewColumns.length + 2" class="text-center text-grey pa-4">
                  {{ $t('paste.noDataToPaste') }}
                </td>
              </tr>
            </tbody>
          </v-table>
        </div>

        <!-- Pagination info if truncated -->
        <v-alert v-if="totalRows > maxPreviewRows" type="info" variant="tonal" density="compact" class="mt-3">
          {{ $t('paste.showingPreview', { shown: maxPreviewRows, total: totalRows }) }}
        </v-alert>
      </v-card-text>

      <v-divider />

      <v-card-actions class="pa-4">
        <v-checkbox
          v-model="skipInvalidRows"
          :label="$t('paste.skipInvalidRows')"
          density="compact"
          hide-details
          :disabled="!validationResult?.invalidRows?.length"
        />
        <v-spacer />
        <v-btn variant="text" @click="handleCancel">
          {{ $t('common.cancel') }}
        </v-btn>
        <v-btn
          color="primary"
          variant="flat"
          @click="handleConfirm"
          :disabled="!canConfirm"
          :loading="loading"
        >
          <v-icon left>mdi-content-paste</v-icon>
          {{ $t('paste.pasteRows', { count: rowsToInsert }) }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  parsedData: {
    type: Object,
    default: null
  },
  convertedRows: {
    type: Array,
    default: () => []
  },
  validationResult: {
    type: Object,
    default: null
  },
  columnMapping: {
    type: Object,
    default: null
  },
  gridColumns: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue', 'confirm', 'cancel'])

const { t } = useI18n()

const skipInvalidRows = ref(true)
const maxPreviewRows = 50

// Computed
const showColumnMapping = computed(() => props.columnMapping !== null)

const unmappedColumns = computed(() => {
  return props.columnMapping?.unmappedClipboard || []
})

const previewColumns = computed(() => {
  return props.gridColumns.filter(col => col.field && col.field !== 'actions')
})

const previewRows = computed(() => {
  const rows = props.convertedRows || []

  // Mark rows with errors
  const invalidRowIndexes = new Set(
    (props.validationResult?.invalidRows || []).map(r => r.rowIndex)
  )

  return rows.slice(0, maxPreviewRows).map((row, idx) => ({
    ...row,
    _hasErrors: invalidRowIndexes.has(idx)
  }))
})

const totalRows = computed(() => props.convertedRows?.length || 0)

const rowsToInsert = computed(() => {
  if (skipInvalidRows.value) {
    return props.validationResult?.totalValid || 0
  }
  return totalRows.value
})

const canConfirm = computed(() => {
  if (skipInvalidRows.value) {
    return (props.validationResult?.totalValid || 0) > 0
  }
  return totalRows.value > 0
})

// Methods
const getCellClass = (row, col) => {
  const classes = []

  if (col.type === 'numericColumn') {
    classes.push('font-weight-medium')
    const value = row[col.field]
    if (typeof value === 'number') {
      if (col.field?.includes('defect') || col.field?.includes('scrap')) {
        if (value > 0) classes.push('text-error')
      } else if (value > 0) {
        classes.push('text-success')
      }
    }
  }

  return classes.join(' ')
}

const formatCellValue = (value, col) => {
  if (value === undefined || value === null) return '-'

  if (col.type === 'numericColumn') {
    if (typeof value === 'number') {
      if (col.field?.includes('hours')) {
        return value.toFixed(2)
      }
      return value.toLocaleString()
    }
  }

  if (col.field?.includes('date')) {
    try {
      const date = new Date(value)
      if (!isNaN(date.getTime())) {
        return date.toLocaleDateString()
      }
    } catch {
      // Return original value if parsing fails
    }
  }

  return value
}

const handleConfirm = () => {
  const rowsToEmit = skipInvalidRows.value
    ? props.validationResult?.validRows || []
    : props.convertedRows || []

  emit('confirm', rowsToEmit)
}

const handleCancel = () => {
  emit('cancel')
  emit('update:modelValue', false)
}

// Reset skipInvalidRows when dialog opens
watch(() => props.modelValue, (isOpen) => {
  if (isOpen) {
    skipInvalidRows.value = true
  }
})
</script>

<style scoped>
.preview-table-container {
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 4px;
  overflow: hidden;
}

.bg-error-lighten-5 {
  background-color: rgba(244, 67, 54, 0.08) !important;
}

.ga-3 {
  gap: 12px;
}
</style>
