<template>
  <v-container fluid>
    <v-row>
      <v-col cols="12">
        <h1 class="text-h3 mb-4">Production Entry</h1>
      </v-col>
    </v-row>

    <v-row>
      <v-col cols="12">
        <DataEntryGrid />
      </v-col>
    </v-row>

    <v-row>
      <v-col cols="12">
        <CSVUpload />
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import DataEntryGrid from '@/components/DataEntryGrid.vue'
import CSVUpload from '@/components/CSVUpload.vue'
</script>
