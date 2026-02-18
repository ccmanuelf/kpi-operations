<template>
  <!-- Analysis Date Range Dialog -->
  <v-dialog v-model="state.showAnalysisDialog" max-width="500">
    <v-card>
      <v-card-title>{{ t('capacityPlanning.workbookDialogs.runCapacityAnalysis') }}</v-card-title>
      <v-card-text>
        <v-row>
          <v-col cols="6">
            <v-text-field
              v-model="state.analysisStartDate"
              :label="t('common.start')"
              type="date"
              variant="outlined"
            />
          </v-col>
          <v-col cols="6">
            <v-text-field
              v-model="state.analysisEndDate"
              :label="t('common.end')"
              type="date"
              variant="outlined"
            />
          </v-col>
        </v-row>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn @click="state.showAnalysisDialog = false">{{ t('common.cancel') }}</v-btn>
        <v-btn color="primary" @click="$emit('runAnalysis')">{{ t('capacityPlanning.workbookDialogs.runAnalysis') }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- Schedule Generation Dialog -->
  <v-dialog v-model="state.showScheduleDialog" max-width="500">
    <v-card>
      <v-card-title>{{ t('capacityPlanning.workbookDialogs.generateProductionSchedule') }}</v-card-title>
      <v-card-text>
        <v-text-field
          v-model="state.scheduleName"
          :label="t('capacityPlanning.dialogs.scheduleName')"
          variant="outlined"
          class="mb-2"
        />
        <v-row>
          <v-col cols="6">
            <v-text-field
              v-model="state.scheduleStartDate"
              :label="t('common.start')"
              type="date"
              variant="outlined"
            />
          </v-col>
          <v-col cols="6">
            <v-text-field
              v-model="state.scheduleEndDate"
              :label="t('common.end')"
              type="date"
              variant="outlined"
            />
          </v-col>
        </v-row>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn @click="state.showScheduleDialog = false">{{ t('common.cancel') }}</v-btn>
        <v-btn color="success" @click="$emit('generateSchedule')">{{ t('capacityPlanning.workbookDialogs.generate') }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- Export Dialog -->
  <v-dialog v-model="state.showExportDialog" max-width="400">
    <v-card>
      <v-card-title>{{ t('capacityPlanning.workbookDialogs.exportWorkbook') }}</v-card-title>
      <v-card-text>
        <v-select
          v-model="state.exportFormat"
          :items="['JSON', 'CSV']"
          :label="t('common.format')"
          variant="outlined"
        />
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn @click="state.showExportDialog = false">{{ t('common.cancel') }}</v-btn>
        <v-btn color="primary" @click="$emit('exportWorkbook')">{{ t('common.export') }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- Import Dialog -->
  <v-dialog v-model="state.showImportDialog" max-width="600">
    <v-card>
      <v-card-title>{{ t('capacityPlanning.workbookDialogs.importData') }}</v-card-title>
      <v-card-text>
        <v-file-input
          v-model="state.importFile"
          :label="t('capacityPlanning.dialogs.selectFile')"
          accept=".json,.csv"
          variant="outlined"
          prepend-icon="mdi-file-upload"
        />
        <v-select
          v-model="state.importTarget"
          :items="state.worksheetOptions"
          :label="t('capacityPlanning.dialogs.targetWorksheet')"
          variant="outlined"
          class="mt-2"
        />
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn @click="state.showImportDialog = false">{{ t('common.cancel') }}</v-btn>
        <v-btn color="primary" @click="$emit('importData')">{{ t('common.import') }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- Reset Confirmation Dialog -->
  <v-dialog v-model="state.showResetDialog" max-width="400">
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
        <v-btn @click="state.showResetDialog = false">{{ t('common.cancel') }}</v-btn>
        <v-btn color="error" @click="$emit('handleReset')">{{ t('common.reset') }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

defineProps({
  state: {
    type: Object,
    required: true,
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
