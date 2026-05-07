<template>
  <v-container fluid data-testid="hold-resume-entry-view">
    <v-row>
      <v-col cols="12">
        <div class="d-flex justify-space-between align-center mb-4">
          <h1 class="text-h3">{{ t('navigation.holdResume') }}</h1>
          <CSVUploadDialogHold />
        </div>
      </v-col>
    </v-row>

    <v-row>
      <v-col cols="12">
        <HoldEntryGrid />
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import HoldEntryGrid from '@/components/grids/HoldEntryGrid.vue'
import CSVUploadDialogHold from '@/components/CSVUploadDialogHold.vue'

const { t } = useI18n()
</script>
