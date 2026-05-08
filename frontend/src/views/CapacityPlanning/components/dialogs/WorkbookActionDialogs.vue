<template>
  <!-- Analysis Date Range Dialog -->
  <v-dialog v-model="showAnalysisDialog" max-width="500">
    <v-card>
      <v-card-title>{{ t('capacityPlanning.workbookDialogs.runCapacityAnalysis') }}</v-card-title>
      <v-card-text>
        <v-row>
          <v-col cols="6">
            <v-text-field
              v-model="analysisStartDate"
              :label="t('common.start')"
              type="date"
              variant="outlined"
            />
          </v-col>
          <v-col cols="6">
            <v-text-field
              v-model="analysisEndDate"
              :label="t('common.end')"
              type="date"
              variant="outlined"
            />
          </v-col>
        </v-row>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn @click="showAnalysisDialog = false">{{ t('common.cancel') }}</v-btn>
        <v-btn color="primary" @click="$emit('runAnalysis')">{{ t('capacityPlanning.workbookDialogs.runAnalysis') }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- Schedule Generation Dialog -->
  <v-dialog v-model="showScheduleDialog" max-width="500">
    <v-card>
      <v-card-title>{{ t('capacityPlanning.workbookDialogs.generateProductionSchedule') }}</v-card-title>
      <v-card-text>
        <v-text-field
          v-model="scheduleName"
          :label="t('capacityPlanning.dialogs.scheduleName')"
          variant="outlined"
          class="mb-2"
        />
        <v-row>
          <v-col cols="6">
            <v-text-field
              v-model="scheduleStartDate"
              :label="t('common.start')"
              type="date"
              variant="outlined"
            />
          </v-col>
          <v-col cols="6">
            <v-text-field
              v-model="scheduleEndDate"
              :label="t('common.end')"
              type="date"
              variant="outlined"
            />
          </v-col>
        </v-row>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn @click="showScheduleDialog = false">{{ t('common.cancel') }}</v-btn>
        <v-btn color="success" @click="$emit('generateSchedule')">{{ t('capacityPlanning.workbookDialogs.generate') }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- Export Dialog -->
  <v-dialog v-model="showExportDialog" max-width="400">
    <v-card>
      <v-card-title>{{ t('capacityPlanning.workbookDialogs.exportWorkbook') }}</v-card-title>
      <v-card-text>
        <v-select
          v-model="exportFormat"
          :items="['JSON', 'CSV']"
          :label="t('common.format')"
          variant="outlined"
        />
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn @click="showExportDialog = false">{{ t('common.cancel') }}</v-btn>
        <v-btn color="primary" @click="$emit('exportWorkbook')">{{ t('common.export') }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- Import Dialog -->
  <v-dialog v-model="showImportDialog" max-width="600">
    <v-card>
      <v-card-title>{{ t('capacityPlanning.workbookDialogs.importData') }}</v-card-title>
      <v-card-text>
        <v-file-input
          v-model="importFile"
          :label="t('capacityPlanning.dialogs.selectFile')"
          accept=".json,.csv"
          variant="outlined"
          prepend-icon="mdi-file-upload"
        />
        <v-select
          v-model="importTarget"
          :items="worksheetOptions"
          :label="t('capacityPlanning.dialogs.targetWorksheet')"
          variant="outlined"
          class="mt-2"
        />
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn @click="showImportDialog = false">{{ t('common.cancel') }}</v-btn>
        <v-btn color="primary" @click="$emit('importData')">{{ t('common.import') }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- Reset Confirmation Dialog -->
  <v-dialog v-model="showResetDialog" max-width="400">
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon start color="warning">mdi-alert-circle</v-icon>
        {{ t('capacityPlanning.workbookDialogs.resetWorkbook') }}
      </v-card-title>
      <v-card-text>
        {{ t('capacityPlanning.workbookDialogs.resetConfirmation') }}
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn @click="showResetDialog = false">{{ t('common.cancel') }}</v-btn>
        <v-btn color="error" @click="$emit('handleReset')">{{ t('common.reset') }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
// All dialog state is two-way bound via defineModel — replaces the prior
// `state` prop pattern that mutated the parent's reactive object directly
// (which Vue 3 flags via `vue/no-mutating-props`). Each model declaration
// matches a `v-model:propName` on the parent.
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

// Dialog visibility flags
const showAnalysisDialog = defineModel('showAnalysisDialog', { type: Boolean, default: false })
const showScheduleDialog = defineModel('showScheduleDialog', { type: Boolean, default: false })
const showExportDialog = defineModel('showExportDialog', { type: Boolean, default: false })
const showImportDialog = defineModel('showImportDialog', { type: Boolean, default: false })
const showResetDialog = defineModel('showResetDialog', { type: Boolean, default: false })

// Analysis dialog fields
const analysisStartDate = defineModel('analysisStartDate', { type: String, default: '' })
const analysisEndDate = defineModel('analysisEndDate', { type: String, default: '' })

// Schedule dialog fields
const scheduleName = defineModel('scheduleName', { type: String, default: '' })
const scheduleStartDate = defineModel('scheduleStartDate', { type: String, default: '' })
const scheduleEndDate = defineModel('scheduleEndDate', { type: String, default: '' })

// Export dialog fields
const exportFormat = defineModel('exportFormat', { type: String, default: 'JSON' })

// Import dialog fields
const importFile = defineModel('importFile', { default: null })
const importTarget = defineModel('importTarget', { type: String, default: '' })

// Read-only options list — stays as a regular prop (no two-way binding needed)
defineProps({
  worksheetOptions: {
    type: Array,
    default: () => [],
  },
})

defineEmits([
  'runAnalysis',
  'generateSchedule',
  'exportWorkbook',
  'importData',
  'handleReset',
])
</script>
