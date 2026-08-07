<template>
  <v-container fluid class="pa-4">
    <v-row>
      <v-col cols="12" md="6">
        <h1 class="text-h3">{{ $t('pivot.title') }}</h1>
        <p class="text-subtitle-1 text-medium-emphasis">{{ $t('pivot.subtitle') }}</p>
      </v-col>
    </v-row>

    <v-tabs v-model="activeTab" class="mt-2">
      <v-tab v-for="view in PIVOT_VIEWS" :key="view.id" :value="view.id"
             :data-testid="`pivot-tab-${view.id}`">
        {{ $t(view.titleKey) }}
      </v-tab>
    </v-tabs>

    <v-window v-model="activeTab">
      <v-window-item v-for="view in PIVOT_VIEWS" :key="view.id" :value="view.id">
        <PivotViewPanel :preset="view" />
      </v-window-item>
    </v-window>
  </v-container>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { PIVOT_VIEWS } from '@/composables/pivotPresets'
import PivotViewPanel from '@/components/PivotViewPanel.vue'

const activeTab = ref('q1')
</script>
