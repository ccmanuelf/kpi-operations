<template>
  <v-container fluid>
    <v-row>
      <v-col cols="12">
        <div class="d-flex justify-space-between align-center mb-4">
          <h1 class="text-h3">{{ t('navigation.productionEntry') }}</h1>
          <CSVUploadDialogProduction />
        </div>
      </v-col>
    </v-row>

    <v-row>
      <v-col cols="12">
        <ProductionEntryGrid />
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import ProductionEntryGrid from '@/components/grids/ProductionEntryGrid.vue'
import CSVUploadDialogProduction from '@/components/CSVUploadDialogProduction.vue'

const { t } = useI18n()
</script>
