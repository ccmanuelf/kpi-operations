<template>
  <v-dialog
    :model-value="modelValue"
    max-width="560"
    data-testid="allocation-editor-dialog"
    @update:model-value="onDialogModelUpdate"
  >
    <v-card v-if="row">
      <v-card-title>
        <v-icon class="mr-2">mdi-clock-time-eight-outline</v-icon>
        {{ t('labor.allocationsTitle') }}
      </v-card-title>

      <v-card-text>
        <div
          v-for="(item, index) in rows"
          :key="index"
          class="d-flex align-center ga-2 mb-3"
          :data-testid="`allocation-row-${index}`"
        >
          <v-select
            v-model="item.category"
            :items="categoryOptions"
            item-title="title"
            item-value="value"
            :label="t('labor.category')"
            variant="outlined"
            density="compact"
            hide-details="auto"
            class="flex-grow-1"
            :data-testid="`allocation-category-select-${index}`"
          />
          <v-text-field
            v-model.number="item.hours"
            type="number"
            min="0"
            step="0.25"
            :label="t('labor.hours')"
            variant="outlined"
            density="compact"
            hide-details="auto"
            style="max-width: 120px"
            :data-testid="`allocation-hours-input-${index}`"
          />
          <v-btn
            icon="mdi-delete-outline"
            variant="text"
            size="small"
            :aria-label="t('labor.removeRow')"
            :data-testid="`allocation-remove-row-btn-${index}`"
            @click="removeRow(index)"
          />
        </div>

        <v-btn
          variant="tonal"
          size="small"
          prepend-icon="mdi-plus"
          data-testid="allocation-add-row-btn"
          @click="addRow"
        >
          {{ t('labor.addRow') }}
        </v-btn>

        <v-alert
          v-if="validation.duplicateCategory"
          type="error"
          variant="tonal"
          density="compact"
          class="mt-3"
          data-testid="allocation-error-duplicate"
        >
          {{ t('labor.duplicateCategory') }}
        </v-alert>
        <v-alert
          v-if="validation.invalidHours"
          type="error"
          variant="tonal"
          density="compact"
          class="mt-3"
          data-testid="allocation-error-invalid-hours"
        >
          {{ t('labor.invalidHours') }}
        </v-alert>
        <v-alert
          v-if="validation.exceedsActual"
          type="error"
          variant="tonal"
          density="compact"
          class="mt-3"
          data-testid="allocation-error-exceeds-actual"
        >
          {{ t('labor.exceedsActualHours') }}
        </v-alert>
        <v-alert
          v-if="errorMessage"
          type="error"
          variant="tonal"
          density="compact"
          class="mt-3"
        >
          {{ errorMessage }}
        </v-alert>

        <div class="text-body-2 text-medium-emphasis mt-3" data-testid="allocation-summary">
          {{ t('labor.allocatedSummary', summary) }}
        </div>
      </v-card-text>

      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" data-testid="allocation-cancel-btn" @click="close">
          {{ t('common.cancel') }}
        </v-btn>
        <v-btn
          color="primary"
          :loading="saving"
          :disabled="!validation.valid"
          data-testid="allocation-save-btn"
          @click="save"
        >
          {{ t('common.save') }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
/**
 * AllocationEditorDialog — Cycle 3 PR-A, Task 7.
 *
 * Small focused component: all row-editing / validation logic lives in the
 * pure composable useAllocationEditor.ts (script-setup testing convention —
 * this SFC has no directly-unit-testable logic of its own). Save submits the
 * full allocations list through the entry-update path (PUT /api/attendance/{id})
 * when the row is already persisted; for a brand-new, not-yet-saved grid row
 * (no attendance_entry_id yet) it only updates local state — the outer grid's
 * batch Save Records flow (useAttendanceGridData::buildPayload) carries the
 * allocations list along on the initial create.
 */
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/services/api'
import { HOUR_CATEGORY_CODES, hourCategoryLabelKey } from '@/constants/laborTaxonomy'
import {
  addAllocationRow,
  removeAllocationRow,
  allocationRowsFromItems,
  toAllocationItems,
  validateAllocations,
  allocationSummary,
  type AllocationRow,
  type AllocationItemPayload,
} from '@/composables/useAllocationEditor'

export interface AllocationDialogRow {
  attendance_entry_id?: string | number
  actual_hours?: number | null
  allocations?: AllocationItemPayload[]
  [key: string]: unknown
}

const props = defineProps<{
  modelValue: boolean
  row: AllocationDialogRow | null
}>()

const emit = defineEmits<{
  (_e: 'update:modelValue', _value: boolean): void
  (_e: 'saved', _payload: { row: AllocationDialogRow; items: AllocationItemPayload[] }): void
}>()

const { t } = useI18n()

const rows = ref<AllocationRow[]>(allocationRowsFromItems(undefined))
const saving = ref(false)
const errorMessage = ref('')

const categoryOptions = computed(() =>
  HOUR_CATEGORY_CODES.map((id) => ({ value: id, title: t(hourCategoryLabelKey(id)) })),
)

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      rows.value = allocationRowsFromItems(props.row?.allocations)
      errorMessage.value = ''
    }
  },
)

const validation = computed(() =>
  validateAllocations(rows.value, props.row?.actual_hours ?? null),
)

const summary = computed(() => allocationSummary(rows.value, props.row?.actual_hours ?? null))

const addRow = (): void => {
  rows.value = addAllocationRow(rows.value)
}

const removeRow = (index: number): void => {
  rows.value = removeAllocationRow(rows.value, index)
}

const close = (): void => emit('update:modelValue', false)

const onDialogModelUpdate = (value: boolean): void => emit('update:modelValue', value)

const save = async (): Promise<void> => {
  if (!validation.value.valid || !props.row) return

  const items = toAllocationItems(rows.value)
  saving.value = true
  errorMessage.value = ''

  try {
    if (props.row.attendance_entry_id) {
      await api.updateAttendanceEntry(props.row.attendance_entry_id, { allocations: items })
    }
    emit('saved', { row: props.row, items })
    close()
  } catch (err) {
    const ax = err as { response?: { data?: { detail?: string } }; message?: string }
    errorMessage.value = ax.response?.data?.detail || ax.message || t('common.error')
  } finally {
    saving.value = false
  }
}
</script>
