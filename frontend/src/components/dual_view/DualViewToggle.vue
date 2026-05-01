<template>
  <v-btn-toggle
    :model-value="dualViewStore.currentMode"
    @update:model-value="onChange"
    mandatory
    density="compact"
    variant="outlined"
    color="primary"
    rounded
  >
    <v-btn value="standard" size="small">
      <v-icon size="small" start>mdi-book-open-outline</v-icon>
      {{ $t('dualView.toggle.standard') }}
    </v-btn>
    <v-btn value="site_adjusted" size="small">
      <v-icon size="small" start>mdi-tune</v-icon>
      {{ $t('dualView.toggle.siteAdjusted') }}
    </v-btn>
  </v-btn-toggle>
</template>

<script setup lang="ts">
import { useDualViewStore, type DualViewMode } from '@/stores/dualViewStore'

const dualViewStore = useDualViewStore()

const onChange = (value: DualViewMode | null) => {
  if (value !== null) {
    dualViewStore.setMode(value)
  }
}
</script>
