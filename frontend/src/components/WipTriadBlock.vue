<template>
  <v-row dense>
    <v-col cols="12" md="4">
      <v-card variant="outlined">
        <v-card-text>
          <div class="text-caption text-medium-emphasis">{{ $t('pivot.wip.avgDaysOnHold') }}</div>
          <div class="text-h5 font-weight-bold">{{ fmt(wipData?.average_days) }}</div>
        </v-card-text>
      </v-card>
    </v-col>
    <v-col cols="12" md="4">
      <v-card variant="outlined">
        <v-card-text>
          <div class="text-caption text-medium-emphasis">{{ $t('pivot.wip.oldestDays') }}</div>
          <div class="text-h5 font-weight-bold">{{ fmt(wipData?.max_days) }}</div>
        </v-card-text>
      </v-card>
    </v-col>
    <v-col cols="12" md="4">
      <v-card variant="outlined">
        <v-card-text>
          <div class="text-caption text-medium-emphasis">{{ $t('pivot.wip.aged15Plus') }}</div>
          <div class="text-h5 font-weight-bold">{{ fmt(wipData?.age_15_plus) }}</div>
        </v-card-text>
      </v-card>
    </v-col>
  </v-row>
</template>

<script setup lang="ts">
/**
 * Q5's WIP headline triad. Not a pivot measure — deliberately sourced from
 * useWipTriadData (a narrow, store-free fetch -- see its own doc comment)
 * rather than the /pivot/holds dataset, per spec §6.
 *
 * Three genuinely distinct fields (fix for a review finding: the original
 * mapping showed `critical_count` and `age_15_plus` under two different
 * labels — both are literally `aging_15_30 + aging_over_30`
 * (frontend/src/services/api/kpi.ts), so two of the three tiles always
 * displayed the identical number):
 *   - average_days -> "avgDaysOnHold": mean age (days) across all WIP
 *     currently on hold.
 *   - max_days     -> "oldestDays": age (days) of the single oldest item
 *     (same field views/kpi/WIPAging.vue shows as "Oldest Item").
 *   - age_15_plus  -> "aged15Plus": count of units aged 15+ days — a
 *     count, not a duration, so it can't collide with the two day-based
 *     metrics above.
 *
 * No distinct server-side "stalled"/"past-due" WIP fields exist —
 * `backend/routes/holds.py::calculate_wip_aging_kpi` (WIPAgingResponse)
 * only returns total_held_quantity/average_aging_days/aging_{0_7,8_14,
 * 15_30,over_30}_days/total_hold_events; there is no backend concept
 * literally named "stalled" or "past due" to map onto.
 */
import { onMounted } from 'vue'
import { useWipTriadData } from '@/composables/useWipTriadData'

const { wipData, fetch } = useWipTriadData()

// Matches usePivotView's displayValue convention: an absent/null reading
// renders as an honest "—", never a fabricated 0.
const fmt = (v: unknown): string => (v === null || v === undefined ? '—' : String(Number(v)))

onMounted(() => fetch())
</script>
