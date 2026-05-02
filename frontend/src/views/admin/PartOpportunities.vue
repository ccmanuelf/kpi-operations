<template>
  <v-container fluid class="pa-4">
    <v-row>
      <v-col cols="12">
        <h1 class="text-h4 mb-2">
          <v-icon class="mr-2">mdi-chart-scatter-plot</v-icon>
          {{ $t('admin.partOpportunities') }}
        </h1>
        <p class="text-subtitle-1 text-grey">
          {{ $t('admin.partOpportunitiesDescription') }}
        </p>
      </v-col>
    </v-row>

    <!-- Info Card -->
    <v-row class="mt-2">
      <v-col cols="12">
        <v-alert type="info" variant="tonal" density="compact">
          <v-icon class="mr-2">mdi-information</v-icon>
          {{ $t('admin.partOpportunitiesInfo') }}
        </v-alert>
      </v-col>
    </v-row>

    <!-- Actions and Filters -->
    <v-row class="mt-4">
      <v-col cols="12" md="4">
        <v-select
          v-model="selectedClient"
          :items="clientOptions"
          item-title="client_name"
          item-value="client_id"
          :label="$t('filters.client')"
          variant="outlined"
          density="comfortable"
          prepend-inner-icon="mdi-domain"
          clearable
          @update:model-value="loadPartOpportunities"
        />
      </v-col>
      <v-col cols="12" md="8" class="d-flex align-center gap-2">
        <v-btn
          color="primary"
          prepend-icon="mdi-plus"
          @click="addRow"
        >
          {{ $t('admin.addPartOpportunity') }}
        </v-btn>
        <v-btn
          color="secondary"
          prepend-icon="mdi-upload"
          @click="openUploadDialog"
        >
          {{ $t('csv.upload') }}
        </v-btn>
        <v-btn
          color="info"
          prepend-icon="mdi-download"
          variant="outlined"
          @click="downloadTemplate"
        >
          {{ $t('csv.downloadTemplate') }}
        </v-btn>
        <v-btn
          color="purple"
          prepend-icon="mdi-help-circle"
          variant="outlined"
          @click="showGuide = true"
        >
          {{ $t('admin.floatingPool.howToUse') }}
        </v-btn>
      </v-col>
    </v-row>

    <!-- Summary Stats -->
    <v-row class="mt-4">
      <v-col cols="12" md="3">
        <v-card variant="tonal" color="primary">
          <v-card-text class="text-center">
            <div class="text-h4 font-weight-bold">{{ partOpportunities.length }}</div>
            <div class="text-caption">{{ $t('admin.totalParts') }}</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3">
        <v-card variant="tonal" color="info">
          <v-card-text class="text-center">
            <div class="text-h4 font-weight-bold">{{ averageOpportunities }}</div>
            <div class="text-caption">{{ $t('admin.avgOpportunities') }}</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3">
        <v-card variant="tonal" color="success">
          <v-card-text class="text-center">
            <div class="text-h4 font-weight-bold">{{ minOpportunities }}</div>
            <div class="text-caption">{{ $t('admin.minOpportunities') }}</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3">
        <v-card variant="tonal" color="warning">
          <v-card-text class="text-center">
            <div class="text-h4 font-weight-bold">{{ maxOpportunities }}</div>
            <div class="text-caption">{{ $t('admin.maxOpportunities') }}</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Part Opportunities Grid -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card>
          <AGGridBase
            :columnDefs="columnDefs"
            :rowData="partOpportunities"
            height="600px"
            :pagination="true"
            :paginationPageSize="25"
            :enableExcelPaste="false"
            entry-type="production"
            @cell-value-changed="onCellValueChanged"
          />
        </v-card>
      </v-col>
    </v-row>

    <!-- Upload CSV Dialog -->
    <v-dialog v-model="uploadDialog" max-width="500" persistent>
      <v-card>
        <v-card-title>
          <v-icon class="mr-2">mdi-upload</v-icon>
          {{ $t('csv.uploadPartOpportunities') }}
        </v-card-title>
        <v-card-text>
          <v-alert type="info" variant="tonal" density="compact" class="mb-4">
            {{ $t('csv.partOpportunitiesInfo') }}
          </v-alert>
          <v-file-input
            v-model="uploadFile"
            :label="$t('csv.selectFile')"
            accept=".csv"
            prepend-icon="mdi-file-delimited"
            variant="outlined"
            show-size
          />
          <v-checkbox
            v-model="replaceExisting"
            :label="$t('csv.replaceExisting')"
            :hint="$t('csv.replaceExistingHint')"
            persistent-hint
            color="warning"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="closeUploadDialog">{{ $t('common.cancel') }}</v-btn>
          <v-btn
            color="primary"
            :loading="uploading"
            :disabled="!uploadFile"
            @click="uploadCSV"
          >
            {{ $t('csv.upload') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Delete Confirmation Dialog -->
    <v-dialog v-model="deleteDialog" max-width="400">
      <v-card>
        <v-card-title class="text-error">
          <v-icon class="mr-2">mdi-alert</v-icon>
          {{ $t('common.confirmDelete') }}
        </v-card-title>
        <v-card-text>
          {{ $t('admin.deletePartOpportunityConfirm', { part: deleteTarget?.part_number }) }}
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="deleteDialog = false">{{ $t('common.cancel') }}</v-btn>
          <v-btn color="error" :loading="deleting" @click="deletePartOpportunity">
            {{ $t('common.delete') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- How-to Guide Dialog -->
    <PartOpportunitiesGuide v-model="showGuide" />

    <!-- Snackbar -->
    <v-snackbar v-model="snackbar.show" :color="snackbar.color" :timeout="3000">
      {{ snackbar.message }}
      <template v-slot:actions>
        <v-btn variant="text" @click="snackbar.show = false">{{ $t('common.close') }}</v-btn>
      </template>
    </v-snackbar>
  </v-container>
</template>

<script setup>
/**
 * AdminPartOpportunities — Group E Surface #15 of the entry-interface
 * audit (final Group E surface).
 *
 * Migrated 2026-05-01 from a v-data-table list + create/edit dialog
 * form to an inline AG Grid surface using the same Excel-style
 * autosave pattern established for the Defect Types catalog (Surface
 * #14): existing rows PUT immediately on every cell-value change; new
 * rows accumulate locally until the operator clicks the green Save
 * button in the row's actions column, then POST.
 *
 * Required fields (part_number, client_id, opportunities_per_unit > 0)
 * validated client-side before POST. part_number and client_id are
 * read-only after creation (matches legacy "disabled when editing"
 * semantics for these natural-key fields).
 *
 * The CSV upload, delete confirmation, and how-to guide dialogs
 * remain as standalone dialogs (Exception 3 / Exception 4 surfaces).
 */
import { ref, onMounted } from 'vue'
import AGGridBase from '@/components/grids/AGGridBase.vue'
import { useNotificationStore } from '@/stores/notificationStore'
import { usePartOpportunitiesData } from '@/composables/usePartOpportunitiesData'
import { usePartOpportunitiesForms } from '@/composables/usePartOpportunitiesForms'
import usePartOpportunitiesGridData from '@/composables/usePartOpportunitiesGridData'
import PartOpportunitiesGuide from './components/PartOpportunitiesGuide.vue'

const showGuide = ref(false)
const notificationStore = useNotificationStore()

const {
  selectedClient,
  partOpportunities,
  snackbar,
  clientOptions,
  averageOpportunities,
  minOpportunities,
  maxOpportunities,
  loadClients,
  loadPartOpportunities,
  showSnackbar: _showSnackbar,
} = usePartOpportunitiesData()

const {
  uploadDialog,
  deleteDialog,
  deleteTarget,
  uploading,
  deleting,
  uploadFile,
  replaceExisting,
  confirmDelete,
  deletePartOpportunity,
  openUploadDialog,
  closeUploadDialog,
  uploadCSV,
  downloadTemplate,
} = usePartOpportunitiesForms(selectedClient, loadPartOpportunities, _showSnackbar)

const { columnDefs, addRow, onCellValueChanged } = usePartOpportunitiesGridData({
  selectedClient,
  partOpportunities,
  clientOptions,
  loadPartOpportunities,
  notify: notificationStore,
  onConfirmDelete: confirmDelete,
})

onMounted(() => {
  loadClients()
  loadPartOpportunities()
})
</script>

<style scoped>
.gap-2 {
  gap: 8px;
}
</style>
