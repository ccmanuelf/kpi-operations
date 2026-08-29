<template>
  <v-dialog
    :model-value="modelValue" max-width="400"
    role="alertdialog" aria-modal="true"
    aria-labelledby="delete-dialog-title" aria-describedby="delete-dialog-desc"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <v-card>
      <v-card-title id="delete-dialog-title" class="text-h6">
        {{ blocked ? t('errors.deleteBlockedTitle') : t('common.confirmDelete') }}
      </v-card-title>
      <v-card-text id="delete-dialog-desc">
        <template v-if="blocked">
          {{ t('errors.deleteBlockedIntro') }}
          <ul class="blocked-by-list">
            <li v-for="row in blockers" :key="row.table">{{ row.label }} ({{ row.count }})</li>
          </ul>
          {{ t('errors.deleteBlockedRemedy') }}
        </template>
        <template v-else>
          {{ t('grids.deleteConfirm') }}
          <strong>{{ workOrderId }}</strong>
        </template>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn
          variant="text" :aria-label="t('workOrders.ariaCancelDeletion')"
          @click="$emit('update:modelValue', false)"
        >
          {{ blocked ? t('common.close') : t('common.cancel') }}
        </v-btn>
        <v-btn
          v-if="!blocked"
          color="error" :loading="loading"
          :aria-label="t('workOrders.ariaConfirmDelete')" @click="$emit('confirm')"
        >
          {{ t('common.delete') }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
/**
 * Confirm a work-order delete, or explain why one was refused.
 *
 * Split out of WorkOrderManagement.vue so the refused state is reachable from a
 * test: the view is `<script setup>`, so a spec cannot set `deleteBlockers` from
 * outside, and the previous coverage — a shallowMount asserting `.exists()` —
 * stayed green with the entire blocked-by list deleted.
 *
 * A non-empty `blockers` means the backend refused the delete with a 409. The
 * dialog then stops being a confirmation: keeping the "Are you sure?" copy and
 * an enabled Delete beside the blocking rows reads as though those rows would be
 * deleted too, and the button could only ever repeat the same refusal.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { BlockedByRow } from '@/services/api/structuredErrors'

const props = withDefaults(
  defineProps<{
    modelValue: boolean
    workOrderId?: string
    blockers?: BlockedByRow[]
    loading?: boolean
  }>(),
  { workOrderId: '', blockers: () => [], loading: false },
)

defineEmits<{
  'update:modelValue': [value: boolean]
  confirm: []
}>()

const { t } = useI18n()
const blocked = computed(() => props.blockers.length > 0)
</script>

<style scoped>
.blocked-by-list {
  /* Tailwind's preflight sets `ul { list-style: none }` in the base layer, so a
     bare <ul> renders as unmarked indented lines. Restated because the point of
     this list is that it reads as discrete records. */
  list-style: disc;
  margin: 8px 0;
  padding-left: 20px;
}
</style>
