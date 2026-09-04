<template>
  <v-container fluid class="pa-4">
    <v-row>
      <v-col cols="12">
        <h1 class="text-h4 mb-2">
          <v-icon class="mr-2">mdi-playlist-edit</v-icon>
          {{ t('admin.holdCatalogs.title') }}
        </h1>
        <p class="text-subtitle-1 text-medium-emphasis">
          {{ t('admin.holdCatalogs.subtitle') }}
        </p>
      </v-col>
    </v-row>

    <!-- Client selector -->
    <v-row class="mt-4">
      <v-col cols="12" md="4">
        <v-select
          v-model="selectedClient"
          :items="clients"
          item-title="client_name"
          item-value="client_id"
          :label="t('filters.client')"
          variant="outlined"
          density="comfortable"
          prepend-inner-icon="mdi-domain"
          @update:model-value="reload"
        />
      </v-col>
      <v-col cols="12" md="8" class="d-flex align-center gap-2">
        <v-btn
          color="secondary"
          prepend-icon="mdi-playlist-plus"
          :disabled="!selectedClient || seeding"
          :loading="seeding"
          @click="runSeedDefaults"
        >
          {{ t('admin.holdCatalogs.seedDefaults') }}
        </v-btn>
      </v-col>
    </v-row>

    <!-- Dead-tenant warning: with no catalog, every hold creation is rejected. -->
    <v-row v-if="catalogIsEmpty" class="mt-2">
      <v-col cols="12">
        <v-alert type="warning" variant="tonal" density="compact">
          <v-icon class="mr-2">mdi-alert</v-icon>
          {{ t('admin.holdCatalogs.emptyCatalogWarning') }}
        </v-alert>
      </v-col>
    </v-row>

    <v-row v-else-if="selectedClientInfo" class="mt-2">
      <v-col cols="12">
        <v-alert type="info" variant="tonal" density="compact">
          <strong>{{ selectedClientInfo.client_name }}</strong> —
          {{ t('admin.holdCatalogs.configuredCounts', { statuses: statuses.length, reasons: reasons.length }) }}
        </v-alert>
      </v-col>
    </v-row>

    <template v-if="selectedClient">
      <!-- Statuses -->
      <v-row class="mt-4">
        <v-col cols="12">
          <div class="d-flex align-center mb-2 gap-2">
            <h2 class="text-h6">{{ t('admin.holdCatalogs.statusesHeading') }}</h2>
            <v-spacer />
            <v-btn
              color="primary"
              size="small"
              prepend-icon="mdi-plus"
              @click="addStatusRow"
            >
              {{ t('admin.holdCatalogs.addStatus') }}
            </v-btn>
          </div>
          <v-card>
            <AGGridBase
              :columnDefs="statusColumnDefs"
              :rowData="statuses"
              height="320px"
              :enableExcelPaste="false"
              entry-type="production"
              @cell-value-changed="onStatusCellChanged"
            />
          </v-card>
        </v-col>
      </v-row>

      <!-- Reasons -->
      <v-row class="mt-6">
        <v-col cols="12">
          <div class="d-flex align-center mb-2 gap-2">
            <h2 class="text-h6">{{ t('admin.holdCatalogs.reasonsHeading') }}</h2>
            <v-spacer />
            <v-btn
              color="primary"
              size="small"
              prepend-icon="mdi-plus"
              @click="addReasonRow"
            >
              {{ t('admin.holdCatalogs.addReason') }}
            </v-btn>
          </div>
          <v-card>
            <AGGridBase
              :columnDefs="reasonColumnDefs"
              :rowData="reasons"
              height="380px"
              :enableExcelPaste="false"
              entry-type="production"
              @cell-value-changed="onReasonCellChanged"
            />
          </v-card>
        </v-col>
      </v-row>
    </template>

    <v-row v-else class="mt-4">
      <v-col cols="12">
        <v-card>
          <v-card-text class="text-center pa-8 text-medium-emphasis">
            <v-icon size="48" color="grey">mdi-playlist-edit</v-icon>
            <p class="mt-2">{{ t('admin.holdCatalogs.selectClientToView') }}</p>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Delete confirmation -->
    <v-dialog v-model="deleteDialog" max-width="460">
      <v-card>
        <v-card-title>
          <v-icon class="mr-2" color="error">mdi-delete</v-icon>
          {{ t('admin.holdCatalogs.confirmDeleteTitle') }}
        </v-card-title>
        <v-card-text>
          {{ t('admin.holdCatalogs.confirmDeleteBody', { code: deleteTargetCode }) }}
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="deleteDialog = false">
            {{ t('common.cancel') }}
          </v-btn>
          <v-btn color="error" :loading="deleting" @click="performDelete">
            {{ t('common.delete') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup>
/**
 * HoldCatalogs — per-client hold status/reason catalog administration.
 *
 * Closes the highest-severity half of the "hold catalog has no UI" gap: the
 * backend rejects any hold whose status/reason is not ACTIVE in the client's
 * catalog, so a tenant whose catalog was never seeded could not record a hold
 * at all and had no way to fix it. The Seed Defaults button is that way out;
 * the two grids are the ongoing per-client CRUD the API always supported.
 *
 * Follows the Spreadsheet Standard like AdminDefectTypes: inline AG Grid,
 * autosave PUT on cell change for existing rows, explicit Save for new rows.
 * Writes require the supervisory tier server-side, which is why the route
 * carries `requiresSupervisory` rather than `requiresAdmin`.
 */
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import AGGridBase from '@/components/grids/AGGridBase.vue'
import { useNotificationStore } from '@/stores/notificationStore'
import { useHoldCatalogAdmin } from '@/composables/useHoldCatalogAdmin'
import useHoldCatalogGridData from '@/composables/useHoldCatalogGridData'

const { t } = useI18n()
const notify = useNotificationStore()

const {
  clients,
  selectedClient,
  statuses,
  reasons,
  selectedClientInfo,
  catalogIsEmpty,
  loadClients,
  loadCatalogs,
  seedDefaults,
  deleteEntry,
} = useHoldCatalogAdmin()

const seeding = ref(false)
const deleting = ref(false)
const deleteDialog = ref(false)
const deleteTarget = ref(null)

const deleteTargetCode = computed(
  () => deleteTarget.value?.row?.status_code || deleteTarget.value?.row?.reason_code || '',
)

const confirmDelete = (kind, row) => {
  deleteTarget.value = { kind, row }
  deleteDialog.value = true
}

const reload = async () => {
  try {
    await loadCatalogs()
  } catch {
    notify.showError(t('errors.general'))
  }
}

const {
  columnDefs: statusColumnDefs,
  addRow: addStatusRow,
  onCellValueChanged: onStatusCellChanged,
} = useHoldCatalogGridData({
  kind: 'status',
  selectedClient,
  rows: statuses,
  loadCatalogs: reload,
  notify,
  onConfirmDelete: confirmDelete,
})

const {
  columnDefs: reasonColumnDefs,
  addRow: addReasonRow,
  onCellValueChanged: onReasonCellChanged,
} = useHoldCatalogGridData({
  kind: 'reason',
  selectedClient,
  rows: reasons,
  loadCatalogs: reload,
  notify,
  onConfirmDelete: confirmDelete,
})

const runSeedDefaults = async () => {
  seeding.value = true
  try {
    const result = await seedDefaults()
    if (result) {
      notify.showSuccess(
        t('admin.holdCatalogs.seedResult', {
          statuses: result.statuses_created,
          reasons: result.reasons_created,
          skipped: result.skipped,
        }),
      )
    }
  } catch (error) {
    notify.showError(error?.response?.data?.detail || t('errors.general'))
  } finally {
    seeding.value = false
  }
}

const performDelete = async () => {
  if (!deleteTarget.value?.row?.catalog_id) return
  deleting.value = true
  try {
    await deleteEntry(deleteTarget.value.kind, deleteTarget.value.row.catalog_id)
    notify.showSuccess(t('admin.holdCatalogs.entryDeleted'))
    deleteDialog.value = false
  } catch (error) {
    notify.showError(error?.response?.data?.detail || t('errors.general'))
  } finally {
    deleting.value = false
  }
}

onMounted(async () => {
  try {
    await loadClients()
  } catch {
    notify.showError(t('errors.general'))
  }
})
</script>

<style scoped>
.gap-2 {
  gap: 8px;
}
</style>
