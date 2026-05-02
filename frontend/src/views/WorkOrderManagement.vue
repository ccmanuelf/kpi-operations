<template>
  <v-container fluid>
    <v-skeleton-loader
      v-if="initialLoading"
      type="heading, card, table"
      class="mb-4"
    />
    <template v-else>
      <v-row class="mb-4">
        <v-col cols="12">
          <div class="d-flex justify-space-between align-center flex-wrap ga-2">
            <div>
              <h1 class="text-h4 font-weight-bold">{{ t('workOrders.title') }}</h1>
              <p class="text-body-2 text-medium-emphasis mt-1">
                {{ t('navigation.workOrders') }}
              </p>
            </div>
            <v-btn
              color="primary"
              prepend-icon="mdi-plus"
              :aria-label="t('workOrders.ariaCreateNew')"
              @click="addRow"
            >
              {{ t('common.add') }} {{ t('production.workOrder') }}
            </v-btn>
          </div>
        </v-col>
      </v-row>
      <v-row class="mb-4" role="region" :aria-label="t('workOrders.ariaStatsSummary')">
        <v-col cols="12" sm="6" md="3">
          <v-card class="pa-4" variant="tonal" color="primary" role="article" aria-labelledby="stat-total-label">
            <div class="d-flex align-center">
              <v-avatar color="primary" size="48" class="mr-4">
                <v-icon aria-hidden="true">mdi-clipboard-list</v-icon>
              </v-avatar>
              <div>
                <div class="text-h5 font-weight-bold" aria-live="polite">{{ summaryStats.total }}</div>
                <div id="stat-total-label" class="text-body-2">{{ t('common.total') }}</div>
              </div>
            </div>
          </v-card>
        </v-col>
        <v-col cols="12" sm="6" md="3">
          <v-card class="pa-4" variant="tonal" color="info" role="article" aria-labelledby="stat-active-label">
            <div class="d-flex align-center">
              <v-avatar color="info" size="48" class="mr-4">
                <v-icon aria-hidden="true">mdi-progress-clock</v-icon>
              </v-avatar>
              <div>
                <div class="text-h5 font-weight-bold" aria-live="polite">{{ summaryStats.active }}</div>
                <div id="stat-active-label" class="text-body-2">{{ t('common.active') }}</div>
              </div>
            </div>
          </v-card>
        </v-col>
        <v-col cols="12" sm="6" md="3">
          <v-card class="pa-4" variant="tonal" color="warning" role="article" aria-labelledby="stat-hold-label">
            <div class="d-flex align-center">
              <v-avatar color="warning" size="48" class="mr-4">
                <v-icon aria-hidden="true">mdi-pause-circle</v-icon>
              </v-avatar>
              <div>
                <div class="text-h5 font-weight-bold" aria-live="polite">{{ summaryStats.onHold }}</div>
                <div id="stat-hold-label" class="text-body-2">{{ t('holds.onHold') }}</div>
              </div>
            </div>
          </v-card>
        </v-col>
        <v-col cols="12" sm="6" md="3">
          <v-card class="pa-4" variant="tonal" color="success" role="article" aria-labelledby="stat-completed-label">
            <div class="d-flex align-center">
              <v-avatar color="success" size="48" class="mr-4">
                <v-icon aria-hidden="true">mdi-check-circle</v-icon>
              </v-avatar>
              <div>
                <div class="text-h5 font-weight-bold" aria-live="polite">{{ summaryStats.completed }}</div>
                <div id="stat-completed-label" class="text-body-2">{{ t('workOrders.completed') }}</div>
              </div>
            </div>
          </v-card>
        </v-col>
      </v-row>
      <v-card class="mb-4" role="search" :aria-label="t('workOrders.ariaFilters')">
        <v-card-text>
          <v-row align="center">
            <v-col cols="12" md="3">
              <v-text-field
                v-model="filters.search"
                prepend-inner-icon="mdi-magnify"
                :label="t('common.search')"
                variant="outlined" density="compact" hide-details clearable
                :aria-label="t('workOrders.ariaSearchWo')"
                @update:model-value="debouncedSearch"
              />
            </v-col>
            <v-col cols="12" md="2">
              <v-select
                v-model="filters.status"
                :items="statusOptions"
                :label="t('common.status')"
                variant="outlined" density="compact" hide-details clearable
                @update:model-value="loadWorkOrders"
              />
            </v-col>
            <v-col cols="12" md="2">
              <v-select
                v-model="filters.priority"
                :items="priorityOptions"
                :label="t('workOrders.priority')"
                variant="outlined" density="compact" hide-details clearable
                @update:model-value="loadWorkOrders"
              />
            </v-col>
            <v-col cols="12" md="2">
              <v-text-field
                v-model="filters.startDate"
                type="date"
                :label="t('filters.startDate')"
                variant="outlined" density="compact" hide-details
                @update:model-value="loadWorkOrders"
              />
            </v-col>
            <v-col cols="12" md="2">
              <v-text-field
                v-model="filters.endDate"
                type="date"
                :label="t('filters.endDate')"
                variant="outlined" density="compact" hide-details
                @update:model-value="loadWorkOrders"
              />
            </v-col>
            <v-col cols="12" md="1">
              <v-btn variant="text" color="primary" :aria-label="t('workOrders.ariaResetFilters')" @click="resetFilters">
                {{ t('common.reset') }}
              </v-btn>
            </v-col>
          </v-row>
        </v-card-text>
      </v-card>
      <v-card>
        <AGGridBase
          :columnDefs="columnDefs"
          :rowData="workOrders"
          height="640px"
          :pagination="true"
          :paginationPageSize="25"
          :enableExcelPaste="false"
          entry-type="production"
          @cell-value-changed="onCellValueChanged"
        />
      </v-card>
    </template>
    <WorkOrderDetailDrawer
      v-model="detailDrawerOpen"
      :work-order="selectedWorkOrder"
      @update="loadWorkOrders"
      @edit="onDrawerEdit"
    />
    <v-dialog
      v-model="deleteDialog" max-width="400"
      role="alertdialog" aria-modal="true"
      aria-labelledby="delete-dialog-title" aria-describedby="delete-dialog-desc"
    >
      <v-card>
        <v-card-title id="delete-dialog-title" class="text-h6">{{ t('common.confirmDelete') }}</v-card-title>
        <v-card-text id="delete-dialog-desc">
          {{ t('grids.deleteConfirm') }}
          <strong>{{ workOrderToDelete?.work_order_id }}</strong>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" :aria-label="t('workOrders.ariaCancelDeletion')" @click="deleteDialog = false">{{ t('common.cancel') }}</v-btn>
          <v-btn color="error" :loading="deleting" :aria-label="t('workOrders.ariaConfirmDelete')" @click="deleteWorkOrder">
            {{ t('common.delete') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup>
/**
 * WorkOrderManagement — Group H Surface #19 of the entry-interface audit.
 *
 * Migrated 2026-05-01 from a v-data-table list + 12-field create/edit
 * dialog form to an inline AG Grid surface. Per the spec's Spreadsheet
 * Standard: operational data with thousands of rows and high churn must
 * use the Excel-style inline-edit pattern, not modal dialogs.
 *
 * Pattern: existing rows autosave PUT on every cell-value change; new
 * rows accumulate locally until the operator clicks the green Save
 * button in the row's actions column, then POST. work_order_id is the
 * natural key — editable only on new rows; locked after creation.
 *
 * Status transitions still flow through the row-action chip (legacy
 * behaviour preserved); the more-actions menu's quick status updates
 * (ON_HOLD / ACTIVE / COMPLETED) keep working through the existing
 * useWorkOrderForms.updateStatus → workflow API path.
 *
 * The detail drawer + delete confirmation dialog remain as standalone
 * dialogs — both qualify under the spec's permitted exceptions
 * (read-only inspector + destructive confirmation).
 */
import { onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import AGGridBase from '@/components/grids/AGGridBase.vue'
import WorkOrderDetailDrawer from '@/components/WorkOrderDetailDrawer.vue'
import { useNotificationStore } from '@/stores/notificationStore'
import { useWorkOrderData } from '@/composables/useWorkOrderData'
import { useWorkOrderForms } from '@/composables/useWorkOrderForms'
import useWorkOrderGridData from '@/composables/useWorkOrderGridData'

const { t } = useI18n()
const notificationStore = useNotificationStore()

const {
  initialLoading, workOrders, selectedWorkOrder, detailDrawerOpen,
  filters, statusOptions, priorityOptions, summaryStats,
  loadWorkOrders, debouncedSearch, resetFilters,
  formatStatus, openDetailDrawer,
} = useWorkOrderData()

const {
  deleteDialog, workOrderToDelete, deleting,
  confirmDelete, deleteWorkOrder,
} = useWorkOrderForms(loadWorkOrders, formatStatus)

const { columnDefs, addRow, onCellValueChanged } = useWorkOrderGridData({
  workOrders,
  loadWorkOrders,
  notify: notificationStore,
  onConfirmDelete: confirmDelete,
  onOpenDetail: openDetailDrawer,
})

// Drawer's "Edit" button used to open the dialog form. Inline editing
// replaces that flow — close the drawer and let the operator edit cells
// directly in the grid.
const onDrawerEdit = () => {
  detailDrawerOpen.value = false
}

onMounted(() => {
  loadWorkOrders()
})
</script>

<style scoped>
.ga-2 {
  gap: 8px;
}
</style>
