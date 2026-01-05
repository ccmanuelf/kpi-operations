<template>
  <v-container fluid>
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
  </v-container>
</template>

<script setup>
import DataEntryGrid from '@/components/DataEntryGrid.vue'
import CSVUploadDialog from '@/components/CSVUploadDialog.vue'
</script>
