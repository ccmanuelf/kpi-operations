<template>
  <v-dialog v-model="dialogModel" max-width="600" persistent>
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon class="mr-2">mdi-export</v-icon>
        Export Simulation Results
      </v-card-title>

      <v-card-text>
        <!-- Export Format -->
        <div class="mb-4">
          <div class="text-subtitle-2 mb-2">Export Format</div>
          <v-btn-toggle v-model="exportFormat" mandatory variant="outlined" density="comfortable">
            <v-btn value="excel">
              <v-icon start>mdi-microsoft-excel</v-icon>
              Excel (.xlsx)
            </v-btn>
            <v-btn value="csv">
              <v-icon start>mdi-file-delimited</v-icon>
              CSV
            </v-btn>
            <v-btn value="json">
              <v-icon start>mdi-code-json</v-icon>
              JSON
            </v-btn>
          </v-btn-toggle>
        </div>

        <!-- Sheets/Data Selection -->
        <div class="mb-4">
          <div class="text-subtitle-2 mb-2">Data to Include</div>
          <v-checkbox
            v-for="sheet in availableSheets"
            :key="sheet.key"
            v-model="selectedSheets"
            :value="sheet.key"
            :label="sheet.label"
            :hint="sheet.hint"
            persistent-hint
            density="compact"
            hide-details="auto"
            class="mb-1"
          />
        </div>

        <v-divider class="my-3" />

        <!-- Options -->
        <div class="mb-4">
          <div class="text-subtitle-2 mb-2">Options</div>

          <v-checkbox
            v-model="options.includeAssumptions"
            label="Include Assumptions & Configuration"
            hint="Add simulation parameters and formulas used"
            persistent-hint
            density="compact"
            hide-details="auto"
          />

          <v-checkbox
            v-model="options.includeTimestamp"
            label="Include timestamp in filename"
            density="compact"
            hide-details="auto"
            class="mt-2"
          />

          <v-text-field
            v-model="customFilename"
            label="Custom filename (optional)"
            variant="outlined"
            density="compact"
            hint="Leave empty for auto-generated name"
            persistent-hint
            class="mt-3"
            clearable
          />
        </div>

        <!-- Preview -->
        <v-alert type="info" variant="tonal" density="compact">
          <div class="d-flex align-center">
            <v-icon class="mr-2">mdi-file-outline</v-icon>
            <div>
              <div class="font-weight-medium">{{ previewFilename }}</div>
              <div class="text-caption">
                {{ selectedSheets.length }} sheet{{ selectedSheets.length !== 1 ? 's' : '' }} selected
              </div>
            </div>
          </div>
        </v-alert>
      </v-card-text>

      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="close">Cancel</v-btn>
        <v-btn
          color="primary"
          variant="elevated"
          :loading="exporting"
          :disabled="selectedSheets.length === 0"
          @click="exportData"
        >
          <v-icon start>mdi-download</v-icon>
          Export
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { exportSimulationToExcel } from '@/utils/excelExport'

const props = defineProps({
  modelValue: Boolean,
  results: Object
})

const emit = defineEmits(['update:modelValue', 'exported'])

// State
const exportFormat = ref('excel')
const selectedSheets = ref(['daily_summary', 'station_performance', 'weekly_capacity', 'per_product'])
const customFilename = ref('')
const exporting = ref(false)

const options = ref({
  includeAssumptions: true,
  includeTimestamp: true
})

// Available sheets
const availableSheets = [
  { key: 'daily_summary', label: 'Daily Summary', hint: 'Overall daily throughput and metrics' },
  { key: 'free_capacity', label: 'Free Capacity', hint: 'Available capacity and operator analysis' },
  { key: 'station_performance', label: 'Station Performance', hint: 'Utilization and queue times per station' },
  { key: 'weekly_capacity', label: 'Weekly Capacity', hint: 'Weekly demand vs capacity comparison' },
  { key: 'per_product', label: 'Per Product Summary', hint: 'Product-level throughput and coverage' },
  { key: 'bundle_metrics', label: 'Bundle Metrics', hint: 'Bundle processing statistics' },
  { key: 'rebalancing', label: 'Rebalancing Suggestions', hint: 'Operator reallocation recommendations' }
]

// Computed
const dialogModel = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const previewFilename = computed(() => {
  if (customFilename.value) {
    return `${customFilename.value}.${getExtension()}`
  }

  let name = 'simulation_results'
  if (options.value.includeTimestamp) {
    const now = new Date()
    const dateStr = now.toISOString().split('T')[0]
    name = `${name}_${dateStr}`
  }
  return `${name}.${getExtension()}`
})

// Methods
const getExtension = () => {
  switch (exportFormat.value) {
    case 'excel': return 'xlsx'
    case 'csv': return 'csv'
    case 'json': return 'json'
    default: return 'xlsx'
  }
}

const close = () => {
  emit('update:modelValue', false)
}

const exportData = async () => {
  if (!props.results) return

  exporting.value = true

  try {
    const filename = customFilename.value
      ? `${customFilename.value}.${getExtension()}`
      : previewFilename.value

    if (exportFormat.value === 'excel') {
      // Use existing Excel export utility
      await exportSimulationToExcel(props.results, {
        filename,
        includeAssumptions: options.value.includeAssumptions
      })
    } else if (exportFormat.value === 'json') {
      // JSON export
      const dataToExport = filterResults()
      const blob = new Blob([JSON.stringify(dataToExport, null, 2)], { type: 'application/json' })
      downloadBlob(blob, filename)
    } else if (exportFormat.value === 'csv') {
      // CSV export - export main summary
      const csv = convertToCSV(props.results.station_performance || [])
      const blob = new Blob([csv], { type: 'text/csv' })
      downloadBlob(blob, filename)
    }

    emit('exported', { format: exportFormat.value, filename })
    close()
  } catch (err) {
    console.error('Export failed:', err)
  } finally {
    exporting.value = false
  }
}

const filterResults = () => {
  if (!props.results) return {}

  const filtered = {}

  // Map sheet keys to result keys
  const keyMap = {
    daily_summary: 'daily_summary',
    free_capacity: 'free_capacity',
    station_performance: 'station_performance',
    weekly_capacity: 'weekly_demand_capacity',
    per_product: 'per_product_summary',
    bundle_metrics: 'bundle_metrics',
    rebalancing: 'rebalancing_suggestions'
  }

  selectedSheets.value.forEach(sheet => {
    const resultKey = keyMap[sheet]
    if (resultKey && props.results[resultKey]) {
      filtered[resultKey] = props.results[resultKey]
    }
  })

  if (options.value.includeAssumptions && props.results.assumption_log) {
    filtered.assumption_log = props.results.assumption_log
  }

  return filtered
}

const convertToCSV = (data) => {
  if (!data || data.length === 0) return ''

  const headers = Object.keys(data[0])
  const rows = data.map(row =>
    headers.map(h => {
      const val = row[h]
      if (typeof val === 'string' && val.includes(',')) {
        return `"${val}"`
      }
      return val
    }).join(',')
  )

  return [headers.join(','), ...rows].join('\n')
}

const downloadBlob = (blob, filename) => {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

// Reset on open
watch(() => props.modelValue, (open) => {
  if (open) {
    customFilename.value = ''
    exporting.value = false
  }
})
</script>

<style scoped>
.v-btn-toggle {
  flex-wrap: wrap;
}
</style>
