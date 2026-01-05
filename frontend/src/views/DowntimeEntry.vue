<template>
  <v-container fluid class="pa-4">
    <v-row>
      <v-col cols="12">
        <DowntimeEntryGrid />
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import DowntimeEntryGrid from '@/components/grids/DowntimeEntryGrid.vue'
</script>

<style scoped>
/* View-specific styles */
</style>
