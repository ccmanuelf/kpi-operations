<template>
  <v-card data-testid="shift-coverage-grid">
    <v-card-title class="bg-primary">
      <div class="d-flex align-center">
        <v-icon class="mr-2">mdi-account-group</v-icon>
        <span class="text-h5">{{ t('coverage.title') }}</span>
      </div>
    </v-card-title>

    <v-card-text>
      <v-row class="mb-1">
        <v-col cols="12" md="3">
          <v-select
            v-model="selectedClient"
            :items="clients"
            item-title="client_name"
            item-value="client_id"
            :label="t('filters.client')"
            variant="outlined"
            density="compact"
            data-testid="coverage-client-select"
            @update:model-value="load"
          />
        </v-col>
        <v-col cols="12" md="2">
          <v-text-field
            v-model="startDate"
            type="date"
            :label="t('coverage.range.from')"
            variant="outlined"
            density="compact"
            @change="load"
          />
        </v-col>
        <v-col cols="12" md="2">
          <v-text-field
            v-model="endDate"
            type="date"
            :label="t('coverage.range.to')"
            variant="outlined"
            density="compact"
            @change="load"
          />
        </v-col>
        <v-col cols="12" md="5" class="d-flex align-center flex-wrap ga-2">
          <v-btn
            v-for="days in RANGE_PRESETS"
            :key="days"
            size="small"
            variant="tonal"
            :data-testid="`coverage-range-${days}`"
            @click="onPreset(days)"
          >
            {{ t('coverage.range.last', { days }) }}
          </v-btn>
          <v-btn
            v-if="canEdit"
            color="primary"
            size="small"
            data-testid="coverage-add-btn"
            @click="openAdd"
          >
            <v-icon start>mdi-plus</v-icon>
            {{ t('coverage.actions.add') }}
          </v-btn>
        </v-col>
      </v-row>

      <v-row v-if="loaded && rows.length" class="mb-2">
        <v-col cols="12" md="3">
          <v-chip label data-testid="coverage-count-chip">
            {{ t('coverage.summary.records') }}: {{ rows.length }}
          </v-chip>
        </v-col>
        <v-col cols="12" md="3">
          <v-chip label data-testid="coverage-average-chip">
            {{ t('coverage.summary.average') }}: {{ averageCoverage }}%
          </v-chip>
        </v-col>
        <v-col cols="12" md="6">
          <v-chip
            :color="shortfalls.length ? 'error' : 'success'"
            label
            data-testid="coverage-shortfall-chip"
            :title="t('coverage.summary.shortfallHint', { threshold: SHORTFALL_THRESHOLD })"
          >
            <v-icon start size="small">mdi-alert-circle-outline</v-icon>
            {{ t('coverage.summary.shortfalls') }}: {{ shortfalls.length }}
          </v-chip>
        </v-col>
      </v-row>

      <v-alert
        v-if="!canEdit"
        type="info"
        variant="tonal"
        density="compact"
        class="mb-3"
        data-testid="coverage-readonly-alert"
      >
        {{ t('coverage.hints.readOnly') }}
      </v-alert>

      <v-alert
        v-else-if="!canDelete"
        type="info"
        variant="tonal"
        density="compact"
        class="mb-3"
        data-testid="coverage-delete-restricted-alert"
      >
        {{ t('coverage.hints.deleteRestricted') }}
      </v-alert>

      <v-alert type="info" variant="tonal" density="compact" class="mb-3">
        {{ t('coverage.hints.derived') }}
      </v-alert>

      <v-alert
        v-if="staleAfterWrite"
        type="warning"
        variant="tonal"
        density="compact"
        class="mb-3"
        data-testid="coverage-stale-alert"
      >
        {{ t('coverage.hints.staleAfterWrite') }}
      </v-alert>

      <v-alert
        v-if="error"
        type="error"
        variant="tonal"
        density="compact"
        class="mb-3"
        data-testid="coverage-error-alert"
      >
        {{ error.detail ?? t(error.key) }}
      </v-alert>

      <div v-if="!selectedClient" class="text-medium-emphasis pa-4" data-testid="coverage-no-client">
        {{ t('coverage.selectClient') }}
      </div>

      <div
        v-else-if="loaded && !rows.length"
        class="text-medium-emphasis pa-4"
        data-testid="coverage-empty"
      >
        {{ t('coverage.noRows') }}
      </div>

      <AGGridBase
        v-else
        :columnDefs="columnDefs"
        :rowData="rows"
        height="560px"
        :enableExcelPaste="false"
        :pagination="true"
        :paginationPageSize="100"
        entry-type="coverage"
        @cell-value-changed="onCellValueChanged"
      />

      <div v-if="canDelete && rows.length" class="mt-3">
        <v-select
          v-model="rowToDelete"
          :items="rows"
          :item-title="deleteLabel"
          item-value="coverage_id"
          return-object
          :label="t('coverage.actions.delete')"
          variant="outlined"
          density="compact"
          clearable
          data-testid="coverage-delete-select"
        />
        <v-btn
          color="error"
          variant="tonal"
          size="small"
          :disabled="!rowToDelete"
          data-testid="coverage-delete-btn"
          @click="showDeleteDialog = true"
        >
          <v-icon start>mdi-delete</v-icon>
          {{ t('coverage.actions.delete') }}
        </v-btn>
      </div>
    </v-card-text>

    <v-dialog v-model="showAddDialog" max-width="520">
      <v-card data-testid="coverage-add-dialog">
        <v-card-title>{{ t('coverage.dialog.addTitle') }}</v-card-title>
        <v-card-text>
          <v-text-field
            v-model="draft.coverage_date"
            type="date"
            :label="t('coverage.fields.date')"
            variant="outlined"
            density="compact"
          />
          <v-select
            v-model="draft.shift_id"
            :items="shiftsForClient"
            item-title="shift_name"
            item-value="shift_id"
            :label="t('coverage.fields.shift')"
            variant="outlined"
            density="compact"
          />
          <v-text-field
            v-model.number="draft.required_employees"
            type="number"
            min="1"
            :label="t('coverage.fields.required')"
            variant="outlined"
            density="compact"
          />
          <v-text-field
            v-model.number="draft.actual_employees"
            type="number"
            min="0"
            :label="t('coverage.fields.actual')"
            variant="outlined"
            density="compact"
          />
          <v-textarea
            v-model="draft.notes"
            :label="t('coverage.fields.notes')"
            variant="outlined"
            density="compact"
            rows="2"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="showAddDialog = false">
            {{ t('coverage.actions.cancel') }}
          </v-btn>
          <v-btn
            color="primary"
            :loading="saving"
            :disabled="!draftIsComplete"
            data-testid="coverage-add-confirm"
            @click="confirmAdd"
          >
            {{ t('coverage.actions.save') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="showDeleteDialog" max-width="480">
      <v-card data-testid="coverage-delete-dialog">
        <v-card-title>{{ t('coverage.dialog.deleteTitle') }}</v-card-title>
        <v-card-text v-if="rowToDelete">
          {{
            t('coverage.dialog.deleteBody', {
              shift: shiftName(rowToDelete.shift_id),
              date: rowToDelete.coverage_date,
            })
          }}
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="showDeleteDialog = false">
            {{ t('coverage.actions.cancel') }}
          </v-btn>
          <v-btn
            color="error"
            :loading="saving"
            data-testid="coverage-delete-confirm"
            @click="confirmDelete"
          >
            {{ t('coverage.actions.delete') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'

import AGGridBase from './AGGridBase.vue'
import useShiftCoverageGrid, {
  RANGE_PRESETS,
  SHORTFALL_THRESHOLD,
  type CoverageRow,
} from '@/composables/useShiftCoverageGrid'

const { t } = useI18n()

const {
  clients,
  shiftsForClient,
  selectedClient,
  rows,
  startDate,
  endDate,
  loaded,
  saving,
  staleAfterWrite,
  error,
  canEdit,
  canDelete,
  shortfalls,
  averageCoverage,
  columnSpecs,
  shiftName,
  applyRange,
  loadClients,
  loadShifts,
  load,
  create,
  update,
  remove,
} = useShiftCoverageGrid()

const showAddDialog = ref(false)
const showDeleteDialog = ref(false)
const rowToDelete = ref<CoverageRow | null>(null)

const draft = reactive<Partial<CoverageRow>>({
  coverage_date: new Date().toISOString().slice(0, 10),
  shift_id: undefined,
  required_employees: undefined,
  actual_employees: undefined,
  notes: '',
})

const draftIsComplete = computed(
  () =>
    Boolean(draft.coverage_date) &&
    draft.shift_id != null &&
    Number(draft.required_employees) > 0 &&
    draft.actual_employees != null &&
    Number(draft.actual_employees) >= 0,
)

/**
 * Specs -> AG Grid defs. The composable stays free of `useI18n` so its logic
 * (which columns are editable, and for whom) can be unit tested without a Vue
 * app context; resolving the header keys belongs here, where there is one.
 */
const columnDefs = computed(() =>
  columnSpecs.value.map((spec) => ({
    headerName: t(spec.headerKey),
    field: spec.field,
    editable: spec.editable,
    width: spec.width,
    minWidth: spec.minWidth,
    flex: spec.flex,
    pinned: spec.pinned,
    sortable: true,
    ...(spec.editor === 'number'
      ? { cellEditor: 'agNumberCellEditor', cellEditorParams: spec.editorParams }
      : {}),
    ...(spec.editor === 'text' ? { cellEditor: 'agTextCellEditor' } : {}),
    ...(spec.format === 'shift'
      ? { valueFormatter: (p: { value: number }) => shiftName(p.value) }
      : {}),
    ...(spec.format === 'percent'
      ? {
          valueFormatter: (p: { value: number }) =>
            p.value == null ? '' : `${Number(p.value).toFixed(1)}%`,
        }
      : {}),
    ...(spec.shortfallBelow != null
      ? {
          cellClassRules: {
            'coverage-shortfall': (p: { value: number }) =>
              Number(p.value) < (spec.shortfallBelow as number),
          },
        }
      : {}),
  })),
)

const deleteLabel = (row: CoverageRow): string =>
  `${row.coverage_date} — ${shiftName(row.shift_id)} (${Number(row.coverage_percentage).toFixed(1)}%)`

const onPreset = async (days: number): Promise<void> => {
  applyRange(days)
  await load()
}

/** Pin the client the dialog was opened for, so a selection that changes
 * while the form is being filled in cannot file the row under another tenant. */
const draftClient = ref<string | null>(null)

const openAdd = (): void => {
  draftClient.value = selectedClient.value == null ? null : String(selectedClient.value)
  showAddDialog.value = true
}

const confirmAdd = async (): Promise<void> => {
  const ok = await create(draft, draftClient.value ?? undefined)
  if (ok) showAddDialog.value = false
}

const confirmDelete = async (): Promise<void> => {
  if (!rowToDelete.value) return
  const ok = await remove(rowToDelete.value)
  if (ok) {
    showDeleteDialog.value = false
    rowToDelete.value = null
  }
}

/** AG Grid hands back the row it mutated; the server owns the percentage, so
 * the edit is sent and the list re-read rather than patched in place. */
const onCellValueChanged = async (event: { data: CoverageRow }): Promise<void> => {
  await update(event.data, event.data)
}

onMounted(async () => {
  await Promise.all([loadClients(), loadShifts()])
})
</script>

<style scoped>
:deep(.coverage-shortfall) {
  color: var(--cds-support-error, #da1e28);
  font-weight: 600;
}
</style>
