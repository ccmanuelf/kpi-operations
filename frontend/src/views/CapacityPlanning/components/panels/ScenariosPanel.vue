<template>
  <v-card>
    <v-card-title class="d-flex align-center">
      <v-icon start>mdi-help-rhombus</v-icon>
      {{ t('capacityPlanning.scenarios.title') }}
      <v-spacer />
      <v-btn
        color="primary"
        size="small"
        variant="elevated"
        :loading="store.isCreatingScenario"
        @click="addRow"
      >
        <v-icon start>mdi-plus</v-icon>
        {{ t('capacityPlanning.scenarios.createScenario') }}
      </v-btn>
      <v-btn
        v-if="selectedScenarioRows.length >= 2"
        color="info"
        size="small"
        variant="outlined"
        class="ml-2"
        @click="compareSelected"
      >
        <v-icon start>mdi-compare</v-icon>
        {{ t('capacityPlanning.scenarios.compareCount', { count: selectedScenarioRows.length }) }}
      </v-btn>
    </v-card-title>
    <v-card-text>
      <div v-if="!scenarios.length" class="text-center pa-8 text-grey">
        <v-icon size="64" color="grey-lighten-1">mdi-help-rhombus</v-icon>
        <div class="text-h6 mt-4">{{ t('capacityPlanning.scenarios.noScenariosTitle') }}</div>
        <div class="text-body-2 mt-2">
          {{ t('capacityPlanning.scenarios.noScenariosDescription') }}
        </div>
        <v-btn
          color="primary"
          variant="tonal"
          class="mt-4"
          @click="addRow"
        >
          {{ t('capacityPlanning.scenarios.createScenario') }}
        </v-btn>
      </div>
      <AGGridBase
        v-else
        :columnDefs="columnDefs"
        :rowData="scenarios"
        height="560px"
        :pagination="true"
        :paginationPageSize="25"
        :enableExcelPaste="false"
        rowSelection="multiRow"
        entry-type="production"
        @grid-ready="onGridReady"
      />
    </v-card-text>

    <v-dialog v-model="deleteDialog" max-width="400">
      <v-card>
        <v-card-title class="text-error">
          <v-icon class="mr-2">mdi-alert</v-icon>
          {{ t('capacityPlanning.scenarios.deleteConfirmTitle') }}
        </v-card-title>
        <v-card-text>
          {{ t('capacityPlanning.scenarios.deleteConfirmMessage') }}
          <strong>{{ deleteTarget?.scenario_name }}</strong>?
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="deleteDialog = false">{{ t('common.cancel') }}</v-btn>
          <v-btn color="error" :loading="deleting" @click="performDelete">
            {{ t('common.delete') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script setup>
/**
 * ScenariosPanel — Group H Surface #20 of the entry-interface audit.
 *
 * Migrated 2026-05-01 from a card grid + 16-input v-dialog form to an
 * inline AG Grid surface. Scenarios are point-in-time records (DRAFT →
 * EVALUATED → APPLIED/REJECTED); the backend has create/run/compare/
 * delete endpoints but no update, so inline editing applies only to
 * new rows. Existing rows expose Run (DRAFT only) / Delete actions.
 *
 * Multi-row selection drives the top-bar Compare button — checking 2+
 * rows enables `store.compareScenarios(...)` which opens the existing
 * comparison dialog.
 *
 * Delete confirmation kept (Exception 4 — destructive action).
 *
 * Note: this commit also fixes a long-standing payload bug —
 * `capacityPlanning.ts:createScenario` was sending `name` instead of
 * `scenario_name`, which the legacy dialog never surfaced because the
 * dialog swallowed errors silently.
 */
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import AGGridBase from '@/components/grids/AGGridBase.vue'
import { useCapacityPlanningStore } from '@/stores/capacityPlanningStore'
import { useNotificationStore } from '@/stores/notificationStore'
import useScenariosGridData from '@/composables/useScenariosGridData'

const { t } = useI18n()

const store = useCapacityPlanningStore()
const notificationStore = useNotificationStore()

const scenarios = computed({
  get: () => store.worksheets.whatIfScenarios.data,
  set: (value) => {
    store.worksheets.whatIfScenarios.data = value
  },
})

const gridApi = ref(null)
const selectedScenarioRows = ref([])

const onGridReady = (params) => {
  gridApi.value = params.api
  if (params.api) {
    params.api.addEventListener?.('selectionChanged', () => {
      selectedScenarioRows.value = params.api.getSelectedRows() || []
    })
  }
}

const deleteDialog = ref(false)
const deleteTarget = ref(null)
const deleting = ref(false)

const onSaveNewRow = async (row) => {
  try {
    await store.createScenario(
      row.scenario_name,
      row.scenario_type,
      { ...(row.parameters || {}) },
    )
    notificationStore.showSuccess(t('capacityPlanning.scenarios.createScenario'))
  } catch (error) {
    notificationStore.showError(
      error?.response?.data?.detail
        || error?.message
        || t('capacityPlanning.scenarios.errors.createFailed'),
    )
    throw error
  }
}

const onRunRow = async (row) => {
  try {
    await store.runScenario(row.id || row._id)
  } catch (error) {
    notificationStore.showError(
      error?.response?.data?.detail
        || error?.message
        || t('capacityPlanning.scenarios.errors.runFailed'),
    )
  }
}

const onConfirmDelete = (row) => {
  deleteTarget.value = row
  deleteDialog.value = true
}

const performDelete = async () => {
  if (!deleteTarget.value) return
  deleting.value = true
  try {
    await store.deleteScenario(deleteTarget.value.id || deleteTarget.value._id)
    deleteDialog.value = false
    deleteTarget.value = null
  } catch (error) {
    notificationStore.showError(
      error?.response?.data?.detail
        || error?.message
        || t('capacityPlanning.scenarios.errors.deleteFailed'),
    )
  } finally {
    deleting.value = false
  }
}

const compareSelected = async () => {
  const ids = selectedScenarioRows.value
    .map((r) => r.id || r._id)
    .filter((id) => typeof id === 'number')
  if (ids.length < 2) return
  try {
    await store.compareScenarios(ids)
  } catch (error) {
    notificationStore.showError(
      error?.response?.data?.detail
        || error?.message
        || t('notifications.workOrders.compareFailed') || 'Failed to compare scenarios',
    )
  }
}

const { columnDefs, addRow } = useScenariosGridData({
  scenarios,
  notify: notificationStore,
  onSaveNewRow,
  onRunRow,
  onConfirmDelete,
})
</script>
