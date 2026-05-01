<template>
  <v-container fluid>
    <v-row>
      <v-col cols="12">
        <div class="d-flex justify-space-between align-center mb-4">
          <h1 class="text-h3">{{ t('navigation.qualityEntry') }}</h1>
          <CSVUploadDialogQuality />
        </div>
      </v-col>
    </v-row>

    <v-row>
      <v-col cols="12">
        <QualityEntryGrid />
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import QualityEntryGrid from '@/components/grids/QualityEntryGrid.vue'
import CSVUploadDialogQuality from '@/components/CSVUploadDialogQuality.vue'

const { t } = useI18n()
</script>
