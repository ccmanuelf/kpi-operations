<template>
  <v-container fluid class="pa-4">
    <v-row>
      <v-col cols="12">
        <div class="d-flex justify-space-between align-center mb-4">
          <h1 class="text-h3">Downtime Entry</h1>
          <CSVUploadDialogDowntime @imported="refreshData" />
        </div>
      </v-col>
    </v-row>

    <v-row>
      <v-col cols="12">
        <DowntimeEntryGrid ref="gridRef" />
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { ref } from 'vue'
import DowntimeEntryGrid from '@/components/grids/DowntimeEntryGrid.vue'
import CSVUploadDialogDowntime from '@/components/CSVUploadDialogDowntime.vue'

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
