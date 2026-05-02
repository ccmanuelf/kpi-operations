<template>
  <v-container fluid class="pa-4">
    <v-row>
      <v-col cols="12">
        <h1 class="text-h4 mb-2">
          <v-icon class="mr-2">mdi-alert-circle-outline</v-icon>
          {{ t('admin.defectTypes.title') }}
        </h1>
        <p class="text-subtitle-1 text-grey">
          {{ t('admin.defectTypes.subtitle') }}
        </p>
      </v-col>
    </v-row>

    <!-- Client Selector and Actions -->
    <v-row class="mt-4">
      <v-col cols="12" md="4">
        <v-select
          v-model="selectedClient"
          :items="clientOptions"
          item-title="client_name"
          item-value="client_id"
          :label="t('admin.defectTypes.selectClientOrGlobal')"
          variant="outlined"
          density="comfortable"
          prepend-inner-icon="mdi-domain"
          @update:model-value="loadDefectTypes"
        >
          <template v-slot:item="{ props, item }">
            <v-list-item v-bind="props">
              <template v-slot:prepend>
                <v-icon :color="item.raw.client_id === GLOBAL_CLIENT_ID ? 'primary' : ''">
                  {{ item.raw.client_id === GLOBAL_CLIENT_ID ? 'mdi-earth' : 'mdi-domain' }}
                </v-icon>
              </template>
            </v-list-item>
          </template>
        </v-select>
      </v-col>
      <v-col cols="12" md="8" class="d-flex align-center gap-2">
        <v-btn
          color="primary"
          prepend-icon="mdi-plus"
          :disabled="!selectedClient"
          @click="addRow"
        >
          {{ t('admin.defectTypes.addDefectType') }}
        </v-btn>
        <v-btn
          color="secondary"
          prepend-icon="mdi-upload"
          :disabled="!selectedClient"
          @click="openUploadDialog"
        >
          {{ t('admin.defectTypes.uploadCsv') }}
        </v-btn>
        <v-btn
          color="info"
          prepend-icon="mdi-download"
          variant="outlined"
          @click="downloadTemplate"
        >
          {{ t('admin.defectTypes.downloadTemplate') }}
        </v-btn>
      </v-col>
    </v-row>

    <!-- Client Info Card -->
    <v-row v-if="selectedClientInfo" class="mt-2">
      <v-col cols="12">
        <v-alert
          :type="isGlobalSelected ? 'warning' : 'info'"
          variant="tonal"
          density="compact"
        >
          <template v-slot:prepend>
            <v-icon>{{ isGlobalSelected ? 'mdi-earth' : 'mdi-domain' }}</v-icon>
          </template>
          <strong>{{ selectedClientInfo.client_name }}</strong> -
          {{ defectTypes.length }} {{ t('admin.defectTypes.defectTypesConfigured') }}
          <span v-if="isGlobalSelected" class="ml-2 text-caption">
            ({{ t('admin.defectTypes.availableToAllClients') }})
          </span>
        </v-alert>
      </v-col>
    </v-row>

    <!-- Defect Types Grid -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card v-if="selectedClient">
          <AGGridBase
            :columnDefs="columnDefs"
            :rowData="defectTypes"
            height="600px"
            :pagination="true"
            :paginationPageSize="25"
            :enableExcelPaste="false"
            entry-type="production"
            @cell-value-changed="onCellValueChanged"
          />
        </v-card>
        <v-card v-else>
          <v-card-text class="text-center pa-8 text-grey">
            <v-icon size="48" color="grey">mdi-alert-circle-outline</v-icon>
            <p class="mt-2">
              {{ t('admin.defectTypes.selectClientToView') }}
            </p>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Upload CSV Dialog (Exception 3 — file picker, not data entry) -->
    <v-dialog v-model="uploadDialog" max-width="500" persistent>
      <v-card>
        <v-card-title>
          <v-icon class="mr-2">mdi-upload</v-icon>
          {{ t('admin.defectTypes.uploadDefectTypesCsv') }}
        </v-card-title>
        <v-card-text>
          <v-alert type="info" variant="tonal" density="compact" class="mb-4">
            {{ t('admin.defectTypes.uploadCsvInfo', { client: selectedClientInfo?.client_name }) }}
          </v-alert>
          <v-file-input
            v-model="uploadFile"
            :label="t('admin.defectTypes.selectCsvFile')"
            accept=".csv"
            prepend-icon="mdi-file-delimited"
            variant="outlined"
            show-size
          />
          <v-checkbox
            v-model="replaceExisting"
            :label="t('admin.defectTypes.replaceExisting')"
            :hint="t('admin.defectTypes.replaceExistingHint')"
            persistent-hint
            color="warning"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="closeUploadDialog">{{ t('common.cancel') }}</v-btn>
          <v-btn
            color="primary"
            :loading="uploading"
            :disabled="!uploadFile"
            @click="uploadCSV"
          >
            {{ t('common.upload') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Delete Confirmation Dialog (Exception 4 — destructive confirmation) -->
    <v-dialog v-model="deleteDialog" max-width="400">
      <v-card>
        <v-card-title class="text-error">
          <v-icon class="mr-2">mdi-alert</v-icon>
          {{ t('admin.defectTypes.confirmDelete') }}
        </v-card-title>
        <v-card-text>
          {{ t('admin.defectTypes.confirmDeleteMessage') }}
          <strong>"{{ deleteTarget?.defect_name }}"</strong>?
          <p class="mt-2 text-grey">{{ t('admin.defectTypes.deleteNote') }}</p>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="deleteDialog = false">{{ t('common.cancel') }}</v-btn>
          <v-btn color="error" :loading="deleting" @click="deleteDefectType">
            {{ t('common.delete') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Snackbar for notifications -->
    <v-snackbar v-model="snackbar.show" :color="snackbar.color" :timeout="3000">
      {{ snackbar.message }}
      <template v-slot:actions>
        <v-btn variant="text" @click="snackbar.show = false">{{ t('common.close') }}</v-btn>
      </template>
    </v-snackbar>
  </v-container>
</template>

<script setup>
/**
 * AdminDefectTypes — Group E Surface #14 of the entry-interface audit.
 *
 * Migrated 2026-05-01 from a v-data-table list + create/edit dialog form
 * to an inline AG Grid surface. Per spec-owner R1 + the spec's "admin
 * config with <5 users" exception list: per-client × many-defect-types
 * is operational data, not config — so it must follow the Spreadsheet
 * Standard.
 *
 * Pattern: existing rows autosave PUT on every cell-value change (Excel-
 * style); new rows accumulate locally until the operator clicks the
 * green Save button in the row's actions column, then POST. Required
 * fields (defect_code, defect_name, severity_default) validated client-
 * side before POST; defect_code is read-only after creation (matches
 * legacy "disabled when editing" semantics).
 *
 * The CSV upload dialog (file picker) and delete confirmation remain as
 * standalone dialogs — both qualify under the spec's permitted exceptions.
 */
import { onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import AGGridBase from '@/components/grids/AGGridBase.vue'
import { useNotificationStore } from '@/stores/notificationStore'
import useDefectTypesData from '@/composables/useDefectTypesData'
import useDefectTypesForms from '@/composables/useDefectTypesForms'
import useDefectTypesGridData from '@/composables/useDefectTypesGridData'

const { t } = useI18n()
const notificationStore = useNotificationStore()

const {
  GLOBAL_CLIENT_ID,
  selectedClient,
  defectTypes,
  clientOptions,
  isGlobalSelected,
  selectedClientInfo,
  loadClients,
  loadDefectTypes,
} = useDefectTypesData()

const {
  uploadDialog,
  deleteDialog,
  deleteTarget,
  uploadFile,
  replaceExisting,
  uploading,
  deleting,
  snackbar,
  showSnackbar,
  confirmDelete,
  deleteDefectType,
  openUploadDialog,
  closeUploadDialog,
  uploadCSV,
  downloadTemplate,
} = useDefectTypesForms(selectedClient, defectTypes, loadDefectTypes)

const { columnDefs, addRow, onCellValueChanged } = useDefectTypesGridData({
  selectedClient,
  defectTypes,
  loadDefectTypes,
  notify: notificationStore,
  onConfirmDelete: confirmDelete,
})

onMounted(async () => {
  try {
    await loadClients()
  } catch {
    showSnackbar(t('errors.general'), 'error')
  }
})
</script>

<style scoped>
.gap-2 {
  gap: 8px;
}
</style>
