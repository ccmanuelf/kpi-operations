<template>
  <v-container fluid>
    <v-skeleton-loader
      v-if="initialLoading"
      type="heading, table"
      class="mb-4"
    />
    <template v-else>
      <v-row>
        <v-col cols="12">
          <div class="d-flex justify-space-between align-center mb-4">
            <h1 class="text-h3">Production Entry</h1>
            <CSVUploadDialog />
          </div>
        </v-col>
      </v-row>

      <v-row>
        <v-col cols="12">
          <DataEntryGrid />
        </v-col>
      </v-row>
    </template>
  </v-container>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import DataEntryGrid from '@/components/DataEntryGrid.vue'
import CSVUploadDialog from '@/components/CSVUploadDialog.vue'

const initialLoading = ref(true)

onMounted(() => {
  // Brief delay to allow child components to initialize
  setTimeout(() => {
    initialLoading.value = false
  }, 300)
})
</script>
