<template>
  <v-card role="region" aria-labelledby="csv-upload-title">
    <v-card-title id="csv-upload-title">{{ $t('csv.title') }}</v-card-title>
    <v-card-text>
      <v-file-input
        v-model="file"
        accept=".csv"
        :label="$t('csv.selectFile')"
        prepend-icon="mdi-file-delimited"
        @change="handleFileChange"
        :loading="loading"
        show-size
        aria-describedby="csv-upload-help"
      ></v-file-input>
      <span id="csv-upload-help" class="sr-only">{{ $t('csv.dragDrop') }}</span>

      <v-alert
        v-if="uploadResult"
        :type="uploadResult.type"
        class="mt-4"
        role="status"
        :aria-live="uploadResult.type === 'error' ? 'assertive' : 'polite'"
      >
        {{ uploadResult.message }}
        <div v-if="uploadResult.details" class="mt-2">
          <strong>{{ $t('common.details') }}:</strong>
          <ul aria-label="Upload statistics">
            <li>{{ $t('csv.rowCount') }}: {{ uploadResult.details.total_rows }}</li>
            <li>{{ $t('dataEntry.rowsValid') }}: {{ uploadResult.details.successful }}</li>
            <li>{{ $t('dataEntry.rowsInvalid') }}: {{ uploadResult.details.failed }}</li>
          </ul>
          <div v-if="uploadResult.details.errors && uploadResult.details.errors.length > 0">
            <strong>{{ $t('common.error') }}:</strong>
            <v-list dense :aria-label="$t('common.error')">
              <v-list-item v-for="(error, idx) in uploadResult.details.errors.slice(0, 5)" :key="idx">
                {{ $t('csv.rowError', { row: error.row, error: error.error }) }}
              </v-list-item>
            </v-list>
          </div>
        </div>
      </v-alert>

      <v-btn
        color="primary"
        @click="uploadFile"
        :disabled="!file || loading"
        :loading="loading"
        class="mt-4"
        :aria-label="$t('common.upload')"
        :aria-busy="loading"
      >
        <v-icon left aria-hidden="true">mdi-upload</v-icon>
        {{ $t('dataEntry.uploadCsv') }}
      </v-btn>

      <v-btn
        text
        @click="downloadTemplate"
        class="mt-4 ml-2"
        :aria-label="$t('dataEntry.downloadTemplate')"
      >
        <v-icon left aria-hidden="true">mdi-download</v-icon>
        {{ $t('dataEntry.downloadTemplate') }}
      </v-btn>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useKPIStore } from '@/stores/kpiStore'

const { t } = useI18n()
const kpiStore = useKPIStore()

const file = ref(null)
const loading = ref(false)
const uploadResult = ref(null)

const handleFileChange = () => {
  uploadResult.value = null
}

const uploadFile = async () => {
  if (!file.value) return

  loading.value = true
  uploadResult.value = null

  const result = await kpiStore.uploadCSV(file.value)

  loading.value = false

  if (result.success) {
    uploadResult.value = {
      type: 'success',
      message: t('csv.success', { count: result.data?.successful || 0 }),
      details: result.data
    }
    file.value = null
  } else {
    uploadResult.value = {
      type: 'error',
      message: result.error || t('csv.error')
    }
  }
}

const downloadTemplate = () => {
  const csvContent = `product_id,shift_id,production_date,work_order_number,units_produced,run_time_hours,employees_assigned,defect_count,scrap_count,notes
1,1,2025-12-31,WO-2025-001,250,7.5,3,5,2,Example entry
2,2,2025-12-31,WO-2025-002,180,7.0,2,3,1,Another example`

  const blob = new Blob([csvContent], { type: 'text/csv' })
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.setAttribute('download', 'production_entry_template.csv')
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}
</script>
