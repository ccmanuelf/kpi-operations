<template>
  <v-container fluid data-testid="shift-coverage-entry-view">
    <v-row>
      <v-col cols="12">
        <div class="d-flex justify-space-between align-center mb-4">
          <div>
            <h1 class="text-h3">{{ t('coverage.title') }}</h1>
            <div class="text-medium-emphasis">{{ t('coverage.subtitle') }}</div>
          </div>
        </div>
      </v-col>
    </v-row>

    <v-row>
      <v-col cols="12">
        <ShiftCoverageGrid />
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import ShiftCoverageGrid from '@/components/grids/ShiftCoverageGrid.vue'

const { t } = useI18n()
</script>
