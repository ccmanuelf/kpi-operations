<template>
  <v-container fluid class="pa-4">
    <v-row>
      <v-col cols="12">
        <div class="d-flex justify-space-between align-center mb-4">
          <h1 class="text-h3">{{ t('holds.title') }}</h1>
          <CSVUploadDialogHold @imported="refreshData" />
        </div>
      </v-col>
    </v-row>

    <v-row>
      <v-col cols="12">
        <HoldEntryGrid ref="gridRef" />
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import HoldEntryGrid from '@/components/grids/HoldEntryGrid.vue'
import CSVUploadDialogHold from '@/components/CSVUploadDialogHold.vue'

const { t } = useI18n()
const gridRef = ref(null)

const refreshData = () => {
  if (gridRef.value && typeof gridRef.value.refreshData === 'function') {
    gridRef.value.refreshData()
  }
}
</script>

<style scoped>
/* View-specific styles */
</style>
