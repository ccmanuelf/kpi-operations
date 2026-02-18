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
              @click="openCreateDialog"
              :aria-label="t('workOrders.ariaCreateNew')"
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
                @update:model-value="debouncedSearch"
                :aria-label="t('workOrders.ariaSearchWo')"
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
              <v-btn variant="text" color="primary" @click="resetFilters" :aria-label="t('workOrders.ariaResetFilters')">
                {{ t('common.reset') }}
              </v-btn>
            </v-col>
          </v-row>
        </v-card-text>
      </v-card>
      <v-card>
        <v-data-table
          :headers="headers"
          :items="workOrders"
          :loading="loading"
          :items-per-page="25"
          :sort-by="[{ key: 'planned_ship_date', order: 'asc' }]"
          class="elevation-0"
          hover
          @click:row="onRowClick"
        >
          <template v-slot:item.work_order_id="{ item }">
            <div class="font-weight-medium text-primary">{{ item.work_order_id }}</div>
          </template>
          <template v-slot:item.style_model="{ item }">
            <div class="text-body-2">{{ item.style_model }}</div>
          </template>
          <template v-slot:item.progress="{ item }">
            <div class="d-flex align-center" style="min-width: 150px;">
              <v-progress-linear
                :model-value="calculateProgress(item)"
                :color="getProgressColor(item)"
                height="8" rounded class="mr-2"
              />
              <span class="text-body-2 text-no-wrap">
                {{ item.actual_quantity }} / {{ item.planned_quantity }}
              </span>
            </div>
          </template>
          <template v-slot:item.progress_pct="{ item }">
            <span class="font-weight-medium">{{ calculateProgress(item).toFixed(1) }}%</span>
          </template>
          <template v-slot:item.status="{ item }">
            <WorkOrderStatusChip
              :work-order-id="item.work_order_id"
              :status="item.status"
              size="small"
              :allow-transitions="true"
              @transitioned="onStatusTransitioned"
              @click.stop
            />
          </template>
          <template v-slot:item.priority="{ item }">
            <v-chip
              v-if="item.priority"
              :color="getPriorityColor(item.priority)"
              size="small" variant="outlined"
            >
              {{ item.priority }}
            </v-chip>
            <span v-else class="text-medium-emphasis">-</span>
          </template>
          <template v-slot:item.planned_ship_date="{ item }">
            <div v-if="item.planned_ship_date" class="d-flex align-center">
              <v-icon v-if="isOverdue(item)" color="error" size="small" class="mr-1">
                mdi-alert-circle
              </v-icon>
              <span :class="{ 'text-error': isOverdue(item) }">
                {{ formatDate(item.planned_ship_date) }}
              </span>
            </div>
            <span v-else class="text-medium-emphasis">{{ $t('common.notSet') }}</span>
          </template>
          <template v-slot:item.actions="{ item }">
            <v-btn icon size="small" variant="text" @click.stop="openDetailDrawer(item)"
              :aria-label="t('workOrders.ariaViewDetails', { id: item.work_order_id })"
              <v-icon aria-hidden="true">mdi-eye</v-icon>
              <v-tooltip activator="parent">{{ $t('workOrders.viewDetails') }}</v-tooltip>
            </v-btn>
            <v-btn icon size="small" variant="text" @click.stop="openEditDialog(item)"
              :aria-label="t('workOrders.ariaEditWo', { id: item.work_order_id })"
              <v-icon aria-hidden="true">mdi-pencil</v-icon>
              <v-tooltip activator="parent">{{ $t('workOrders.edit') }}</v-tooltip>
            </v-btn>
            <v-menu>
              <template v-slot:activator="{ props }">
                <v-btn icon size="small" variant="text" v-bind="props" @click.stop
                  :aria-label="t('workOrders.ariaMoreActions', { id: item.work_order_id })" aria-haspopup="menu">
                  <v-icon aria-hidden="true">mdi-dots-vertical</v-icon>
                </v-btn>
              </template>
              <v-list density="compact">
                <v-list-item v-if="item.status === 'ACTIVE'" prepend-icon="mdi-pause" @click="updateStatus(item, 'ON_HOLD')">
                  <v-list-item-title>{{ t('holds.onHold') }}</v-list-item-title>
                </v-list-item>
                <v-list-item v-if="item.status === 'ON_HOLD'" prepend-icon="mdi-play" @click="updateStatus(item, 'ACTIVE')">
                  <v-list-item-title>{{ t('holds.resumed') }}</v-list-item-title>
                </v-list-item>
                <v-list-item v-if="item.status === 'ACTIVE'" prepend-icon="mdi-check" @click="updateStatus(item, 'COMPLETED')">
                  <v-list-item-title>{{ t('workOrders.completed') }}</v-list-item-title>
                </v-list-item>
                <v-divider />
                <v-list-item prepend-icon="mdi-delete" base-color="error" @click="confirmDelete(item)">
                  <v-list-item-title>{{ t('common.delete') }}</v-list-item-title>
                </v-list-item>
              </v-list>
            </v-menu>
          </template>
        </v-data-table>
      </v-card>
    </template>
    <WorkOrderDetailDrawer
      v-model="detailDrawerOpen"
      :work-order="selectedWorkOrder"
      @update="loadWorkOrders"
      @edit="openEditDialog"
    />
    <v-dialog
      v-model="formDialog" max-width="700" persistent
      role="dialog" aria-modal="true"
      :aria-labelledby="editingWorkOrder ? 'edit-wo-title' : 'create-wo-title'"
    >
      <v-card>
        <v-card-title class="d-flex justify-space-between align-center">
          <span :id="editingWorkOrder ? 'edit-wo-title' : 'create-wo-title'">
            {{ editingWorkOrder ? t('common.edit') + ' ' + t('production.workOrder') : t('common.add') + ' ' + t('production.workOrder') }}
          </span>
          <v-btn icon variant="text" @click="formDialog = false" :aria-label="t('workOrders.ariaCloseDialog')">
            <v-icon aria-hidden="true">mdi-close</v-icon>
          </v-btn>
        </v-card-title>
        <v-card-text>
          <v-form ref="formRef" v-model="formValid">
            <v-row>
              <v-col cols="12" md="6">
                <v-text-field v-model="formData.work_order_id" :label="t('workOrders.workOrderId') + ' *'"
                  variant="outlined" :rules="[rules.required]" :disabled="!!editingWorkOrder" />
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field v-model="formData.style_model" :label="t('production.style') + ' *'"
                  variant="outlined" :rules="[rules.required]" />
              </v-col>
            </v-row>
            <v-row>
              <v-col cols="12" md="6">
                <v-text-field v-model.number="formData.planned_quantity" type="number"
                  :label="t('workOrders.quantityOrdered') + ' *'" variant="outlined" :rules="[rules.required, rules.positive]" />
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field v-model.number="formData.actual_quantity" type="number"
                  :label="t('workOrders.quantityCompleted')" variant="outlined" :rules="[rules.nonNegative]" />
              </v-col>
            </v-row>
            <v-row>
              <v-col cols="12" md="6">
                <v-select v-model="formData.status" :items="statusOptions"
                  :label="t('common.status') + ' *'" variant="outlined" :rules="[rules.required]" />
              </v-col>
              <v-col cols="12" md="6">
                <v-select v-model="formData.priority" :items="priorityOptions"
                  :label="t('workOrders.priority')" variant="outlined" clearable />
              </v-col>
            </v-row>
            <v-row>
              <v-col cols="12" md="6">
                <v-text-field v-model="formData.planned_start_date" type="date"
                  :label="t('workOrders.plannedStart')" variant="outlined" />
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field v-model="formData.planned_ship_date" type="date"
                  :label="t('workOrders.plannedEnd')" variant="outlined" />
              </v-col>
            </v-row>
            <v-row>
              <v-col cols="12" md="6">
                <v-text-field v-model="formData.customer_po_number"
                  :label="t('production.workOrder')" variant="outlined" />
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field v-model.number="formData.ideal_cycle_time" type="number" step="0.01"
                  :label="t('production.cycleTime')" variant="outlined" />
              </v-col>
            </v-row>
            <v-row>
              <v-col cols="12">
                <v-textarea v-model="formData.notes" :label="t('production.notes')"
                  variant="outlined" rows="3" />
              </v-col>
            </v-row>
          </v-form>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="formDialog = false">{{ t('common.cancel') }}</v-btn>
          <v-btn color="primary" :loading="saving" :disabled="!formValid" @click="saveWorkOrder">
            {{ editingWorkOrder ? t('common.update') : t('common.save') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
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
          <v-btn variant="text" @click="deleteDialog = false" :aria-label="t('workOrders.ariaCancelDeletion')">{{ t('common.cancel') }}</v-btn>
          <v-btn color="error" :loading="deleting" @click="deleteWorkOrder" :aria-label="t('workOrders.ariaConfirmDelete')">
            {{ t('common.delete') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup>
import { onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import WorkOrderDetailDrawer from '@/components/WorkOrderDetailDrawer.vue'
import WorkOrderStatusChip from '@/components/workflow/WorkOrderStatusChip.vue'
import { useWorkOrderData } from '@/composables/useWorkOrderData'
import { useWorkOrderForms } from '@/composables/useWorkOrderForms'

const { t } = useI18n()

const {
  initialLoading, loading, workOrders, selectedWorkOrder, detailDrawerOpen,
  filters, statusOptions, priorityOptions, headers, summaryStats,
  loadWorkOrders, debouncedSearch, resetFilters,
  calculateProgress, getProgressColor, formatStatus,
  getPriorityColor, formatDate, isOverdue,
  onRowClick, openDetailDrawer
} = useWorkOrderData()

const {
  formDialog, deleteDialog, editingWorkOrder, workOrderToDelete,
  formRef, formValid, saving, deleting, formData, rules,
  openCreateDialog, openEditDialog, saveWorkOrder,
  updateStatus, onStatusTransitioned, confirmDelete, deleteWorkOrder
} = useWorkOrderForms(loadWorkOrders, formatStatus)

onMounted(() => {
  loadWorkOrders()
})
</script>

<style scoped>
.v-data-table :deep(tbody tr) {
  cursor: pointer;
}
.v-data-table :deep(tbody tr:hover) {
  background-color: rgba(var(--v-theme-primary), 0.04) !important;
}
</style>
