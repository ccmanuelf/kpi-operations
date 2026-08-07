<template>
  <v-row dense>
    <v-col cols="12" md="4">
      <v-card variant="outlined">
        <v-card-text>
          <div class="text-caption text-medium-emphasis">{{ $t('pivot.wip.stalled') }}</div>
          <div class="text-h5 font-weight-bold">{{ wipData?.critical_count || 0 }}</div>
        </v-card-text>
      </v-card>
    </v-col>
    <v-col cols="12" md="4">
      <v-card variant="outlined">
        <v-card-text>
          <div class="text-caption text-medium-emphasis">{{ $t('pivot.wip.old') }}</div>
          <div class="text-h5 font-weight-bold">{{ wipData?.max_days || 0 }}</div>
        </v-card-text>
      </v-card>
    </v-col>
    <v-col cols="12" md="4">
      <v-card variant="outlined">
        <v-card-text>
          <div class="text-caption text-medium-emphasis">{{ $t('pivot.wip.pastDue') }}</div>
          <div class="text-h5 font-weight-bold">{{ wipData?.age_15_plus || 0 }}</div>
        </v-card-text>
      </v-card>
    </v-col>
  </v-row>
</template>

<script setup lang="ts">
/**
 * Q5's WIP headline triad. Not a pivot measure — deliberately sourced from
 * useWIPAgingData (same composable/API surface as views/kpi/WIPAging.vue)
 * rather than the /pivot/holds dataset, per spec §6.
 *
 * critical_count -> "stalled" (WIP past the client's critical aging
 * threshold), max_days -> "old" (age of the single oldest item),
 * age_15_plus -> "pastDue" (count of units aged 15+ days).
 */
import { onMounted } from 'vue'
import useWIPAgingData from '@/composables/useWIPAgingData'

const { wipData, initialize } = useWIPAgingData()

onMounted(() => initialize())
</script>
