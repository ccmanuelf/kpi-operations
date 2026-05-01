<template>
  <v-container fluid class="pa-4" role="main" aria-labelledby="variance-title">
    <!-- Header -->
    <v-row class="mb-2">
      <v-col cols="12" md="8">
        <h1 id="variance-title" class="text-h4">{{ $t('variance.title') }}</h1>
        <p class="text-subtitle-1 text-grey">{{ $t('variance.subtitle') }}</p>
      </v-col>
      <v-col cols="12" md="4" class="d-flex align-center justify-end ga-2">
        <v-text-field
          v-model.number="staleAfterDays"
          type="number"
          density="compact"
          variant="outlined"
          hide-details
          :label="$t('variance.staleThresholdLabel')"
          style="max-width: 220px"
          @change="loadRows"
        />
        <v-btn
          icon="mdi-refresh"
          variant="text"
          @click="loadRows"
          :loading="loading"
          :aria-label="$t('common.refresh')"
        />
      </v-col>
    </v-row>

    <!-- Summary stats -->
    <v-row dense class="mb-4">
      <v-col cols="12" sm="4">
        <v-card variant="outlined">
          <v-card-text class="d-flex align-center ga-3">
            <v-icon size="large" color="primary">mdi-tune</v-icon>
            <div>
              <div class="text-h5 font-weight-bold">{{ rows.length }}</div>
              <div class="text-caption text-medium-emphasis">{{ $t('variance.totalActive') }}</div>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" sm="4">
        <v-card variant="outlined">
          <v-card-text class="d-flex align-center ga-3">
            <v-icon size="large" color="warning">mdi-alert-decagram-outline</v-icon>
            <div>
              <div class="text-h5 font-weight-bold">{{ deviatingCount }}</div>
              <div class="text-caption text-medium-emphasis">{{ $t('variance.deviatingFromDefault') }}</div>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" sm="4">
        <v-card variant="outlined">
          <v-card-text class="d-flex align-center ga-3">
            <v-icon size="large" color="error">mdi-clock-alert-outline</v-icon>
            <div>
              <div class="text-h5 font-weight-bold">{{ staleCount }}</div>
              <div class="text-caption text-medium-emphasis">
                {{ $t('variance.staleCount', { days: staleAfterDays }) }}
              </div>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Error -->
    <v-alert
      v-if="error"
      type="error"
      variant="tonal"
      closable
      class="mb-4"
      @click:close="error = null"
    >
      {{ error }}
    </v-alert>

    <!-- Table -->
    <v-card>
      <v-data-table
        :headers="headers"
        :items="rows"
        :loading="loading"
        :sort-by="[{ key: 'deviation_magnitude', order: 'desc' }]"
        :items-per-page="25"
        density="compact"
        :no-data-text="$t('variance.noData')"
      >
        <template v-slot:item.assumption_name="{ item }">
          <div class="font-weight-medium">{{ item.assumption_name }}</div>
          <div v-if="item.description" class="text-caption text-medium-emphasis">
            {{ item.description }}
          </div>
        </template>

        <template v-slot:item.value="{ item }">
          <code class="text-body-2">{{ formatValue(item.value) }}</code>
        </template>

        <template v-slot:item.default_value="{ item }">
          <code class="text-body-2 text-medium-emphasis">{{ formatValue(item.default_value) }}</code>
        </template>

        <template v-slot:item.deviates_from_default="{ item }">
          <v-chip
            v-if="item.deviates_from_default"
            color="warning"
            size="x-small"
            variant="tonal"
          >
            {{ formatMagnitude(item.deviation_magnitude, item.assumption_name) }}
          </v-chip>
          <v-chip v-else color="success" size="x-small" variant="tonal">
            {{ $t('variance.matchesDefault') }}
          </v-chip>
        </template>

        <template v-slot:item.approved_at="{ item }">
          <div v-if="item.approved_at">
            {{ formatDate(item.approved_at) }}
            <div class="text-caption text-medium-emphasis">
              {{ $t('variance.daysAgo', { count: item.days_since_review || 0 }) }}
            </div>
          </div>
          <span v-else class="text-medium-emphasis">—</span>
        </template>

        <template v-slot:item.is_stale="{ item }">
          <v-icon v-if="item.is_stale" color="error" size="small">mdi-clock-alert</v-icon>
          <v-icon v-else color="success" size="small">mdi-check</v-icon>
        </template>
      </v-data-table>
    </v-card>
  </v-container>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import {
  getVarianceReport,
  type VarianceRow,
} from '@/services/api/calculationAssumptions'

const { t } = useI18n()

const rows = ref<VarianceRow[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const staleAfterDays = ref(365)

const headers = computed(() => [
  { title: t('variance.colClient'), key: 'client_id', sortable: true },
  { title: t('variance.colAssumption'), key: 'assumption_name', sortable: true },
  { title: t('variance.colValue'), key: 'value', sortable: false },
  { title: t('variance.colDefault'), key: 'default_value', sortable: false },
  { title: t('variance.colDeviation'), key: 'deviates_from_default', sortable: true },
  { title: t('variance.colMagnitude'), key: 'deviation_magnitude', sortable: true, align: 'end' as const },
  { title: t('variance.colApprovedBy'), key: 'approved_by', sortable: true },
  { title: t('variance.colApprovedAt'), key: 'approved_at', sortable: true },
  { title: t('variance.colStale'), key: 'is_stale', sortable: true, align: 'center' as const },
])

const deviatingCount = computed(() => rows.value.filter((r) => r.deviates_from_default).length)
const staleCount = computed(() => rows.value.filter((r) => r.is_stale).length)

const loadRows = async () => {
  loading.value = true
  error.value = null
  try {
    const response = await getVarianceReport(staleAfterDays.value)
    rows.value = response.data
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to load variance report'
    rows.value = []
  } finally {
    loading.value = false
  }
}

const formatValue = (value: unknown): string => {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

const formatMagnitude = (magnitude: number, name: string): string => {
  if (name === 'otd_carrier_buffer_pct') {
    return `+${magnitude.toFixed(1)}%`
  }
  return t('variance.deviates')
}

const formatDate = (iso: string): string => new Date(iso).toLocaleDateString()

onMounted(() => {
  loadRows()
})
</script>
