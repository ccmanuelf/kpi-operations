<template>
  <v-container fluid class="pa-4">
    <v-row>
      <v-col cols="12">
        <h1 class="text-h4 mb-2">
          <v-icon class="mr-2">mdi-clock-outline</v-icon>
          {{ t('admin.shifts.title') }}
        </h1>
        <p class="text-subtitle-1 text-grey">
          {{ t('admin.shifts.subtitle') }}
        </p>
      </v-col>
    </v-row>

    <v-row class="mt-4">
      <v-col cols="12" md="4">
        <v-select
          v-model="selectedClient"
          :items="clientOptions"
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
        <v-btn color="primary" prepend-icon="mdi-plus" :disabled="!selectedClient" @click="addRow">
          {{ t('admin.shifts.addShift') }}
        </v-btn>
        <span v-if="!selectedClient" class="text-caption text-grey">
          {{ t('admin.shifts.selectClientToAdd') }}
        </span>
        <v-spacer />
        <v-switch
          v-model="includeInactive"
          :label="t('admin.shifts.showInactive')"
          density="compact"
          hide-details
          color="primary"
          data-testid="show-inactive"
          @update:model-value="reload"
        />
      </v-col>
    </v-row>

    <!-- The onboarding checklist's first step reports on exactly this state. -->
    <v-row v-if="noShiftsConfigured" class="mt-2">
      <v-col cols="12">
        <v-alert type="warning" variant="tonal" density="compact">
          <v-icon class="mr-2">mdi-alert</v-icon>
          {{ t('admin.shifts.noShiftsWarning') }}
        </v-alert>
      </v-col>
    </v-row>

    <v-row class="mt-4">
      <v-col cols="12">
        <v-card>
          <AGGridBase
            :columnDefs="columnDefs"
            :rowData="shifts"
            height="520px"
            :enableExcelPaste="false"
            entry-type="production"
            @cell-value-changed="onCellValueChanged"
          />
        </v-card>
      </v-col>
    </v-row>

    <!-- Overlap pre-check: the backend permits overlaps but reports them, so
         this asks rather than blocks. -->
    <v-dialog v-model="overlapDialog" max-width="520" persistent>
      <v-card>
        <v-card-title>
          <v-icon class="mr-2" color="warning">mdi-alert</v-icon>
          {{ t('admin.shifts.overlapTitle') }}
        </v-card-title>
        <v-card-text>
          <p class="mb-3">{{ t('admin.shifts.overlapBody') }}</p>
          <ul class="pl-4">
            <li v-for="o in overlapList" :key="o.shift_id">
              <strong>{{ o.shift_name }}</strong>
              {{ t('admin.shifts.timeRange', { start: o.start_time, end: o.end_time }) }}
            </li>
          </ul>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="resolveOverlap(false)">
            {{ t('common.cancel') }}
          </v-btn>
          <v-btn color="warning" @click="resolveOverlap(true)">
            {{ t('admin.shifts.saveAnyway') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="deleteDialog" max-width="460">
      <v-card>
        <v-card-title>
          <v-icon class="mr-2" color="error">mdi-delete</v-icon>
          {{ t('admin.shifts.confirmDeleteTitle') }}
        </v-card-title>
        <v-card-text>
          {{ t('admin.shifts.confirmDeleteBody', { name: deleteTarget?.shift_name ?? '' }) }}
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
  </v-container>
</template>

<script setup>
/**
 * ShiftsAdmin — CRUD for the SHIFT master-data table.
 *
 * Closes the shift gap in docs/audit/backend-capability-without-ui.md. Every
 * production, downtime, attendance, quality and hold row is stamped with a
 * shift, and the shift dropdown appears on every data-entry grid — yet the
 * only shift call in the whole frontend was a read. Shifts existed solely
 * because the seeder wrote them; on a real deployment the table would be
 * empty and unfillable.
 *
 * It also makes the onboarding checklist's FIRST step completable. That step
 * ("configure shifts") pointed at /admin/settings, which has no shift UI at
 * all, so the item could never be ticked through the product.
 *
 * The overlap dialog surfaces POST /shifts/check-overlap, built for exactly
 * this and never called. Overlaps are permitted by the backend, so this asks
 * rather than blocks.
 */
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import AGGridBase from '@/components/grids/AGGridBase.vue'
import { useNotificationStore } from '@/stores/notificationStore'
import { useShiftAdmin } from '@/composables/useShiftAdmin'
import useShiftAdminGridData from '@/composables/useShiftAdminGridData'

const { t } = useI18n()
const notify = useNotificationStore()

const {
  clients,
  selectedClient,
  shifts,
  includeInactive,
  noShiftsConfigured,
  loadClients,
  loadShifts,
  removeShift,
} = useShiftAdmin()

const deleting = ref(false)
const deleteDialog = ref(false)
const deleteTarget = ref(null)
const overlapDialog = ref(false)
const overlapList = ref([])
let overlapResolver = null

const clientOptions = computed(() => [
  { client_id: null, client_name: t('common.all') },
  ...clients.value,
])

const showAllClients = computed(() => !selectedClient.value)

const reload = async () => {
  try {
    await loadShifts()
  } catch {
    notify.showError(t('errors.general'))
  }
}

const confirmDelete = (row) => {
  deleteTarget.value = row
  deleteDialog.value = true
}

const confirmOverlap = (overlaps) => {
  // Two rows can be saved concurrently. Without this, the second prompt would
  // overwrite the first's resolver, leaving that save awaiting a promise that
  // never settles — stuck mid-save with its row flagged saving forever.
  overlapResolver?.(false)
  overlapList.value = overlaps
  overlapDialog.value = true
  return new Promise((resolve) => {
    overlapResolver = resolve
  })
}

const resolveOverlap = (saveAnyway) => {
  overlapDialog.value = false
  overlapResolver?.(saveAnyway)
  overlapResolver = null
}

const { columnDefs, addRow, onCellValueChanged } = useShiftAdminGridData({
  selectedClient,
  shifts,
  loadShifts: reload,
  notify,
  onConfirmDelete: confirmDelete,
  confirmOverlap,
  showAllClients,
})

const performDelete = async () => {
  if (!deleteTarget.value?.shift_id) return
  deleting.value = true
  try {
    await removeShift(deleteTarget.value.shift_id)
    notify.showSuccess(t('admin.shifts.shiftDeleted'))
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
  await reload()
})
</script>

<style scoped>
.gap-2 {
  gap: 8px;
}
</style>
