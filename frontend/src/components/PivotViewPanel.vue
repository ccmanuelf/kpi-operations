<template>
  <div class="mt-4">
    <v-row density="compact">
      <v-col cols="6" md="2">
        <v-select v-model="view.bucket.value" :items="bucketItems" item-title="title" item-value="value"
                  :label="$t('pivot.bucket')" density="compact" variant="outlined"
                  data-testid="pivot-bucket-select" @update:model-value="view.refresh" />
      </v-col>
      <v-col cols="6" md="2">
        <v-select v-model="view.groupBy.value" :items="groupingItems" item-title="title" item-value="value"
                  :label="$t('pivot.groupBy')" density="compact" variant="outlined"
                  data-testid="pivot-grouping-select" @update:model-value="view.refresh" />
      </v-col>
      <v-col cols="6" md="2">
        <v-text-field v-model="view.startDate.value" type="date" :label="$t('filters.startDate')"
                      density="compact" variant="outlined" @change="view.refresh" />
      </v-col>
      <v-col cols="6" md="2">
        <v-text-field v-model="view.endDate.value" type="date" :label="$t('filters.endDate')"
                      density="compact" variant="outlined" @change="view.refresh" />
      </v-col>
      <v-col cols="12" md="2">
        <v-btn color="primary" block :loading="view.downloading.value" data-testid="pivot-download"
               @click="view.download">
          <v-icon start>mdi-download</v-icon>{{ $t('pivot.downloadCsv') }}
        </v-btn>
      </v-col>
    </v-row>

    <v-alert v-if="view.error.value" type="error" density="compact" class="mb-2">{{ view.error.value }}</v-alert>

    <v-progress-linear :active="view.loading.value" indeterminate color="primary" class="mb-2" />

    <AGGridBase :column-defs="columnDefs" :row-data="gridRows"
                :enable-excel-paste="false" :enable-csv-import="false" :enable-export="false" />

    <WipTriadBlock v-if="preset.showWipTriad" class="mt-4" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import AGGridBase from '@/components/grids/AGGridBase.vue'
import WipTriadBlock from '@/components/WipTriadBlock.vue'
import { BUCKET_LABEL_KEYS, VALID_BUCKETS, groupLabel, visibleColumns, type PivotViewPreset } from '@/composables/pivotPresets'
import { displayValue, usePivotView } from '@/composables/usePivotView'

const props = defineProps<{ preset: PivotViewPreset }>()
const { t } = useI18n()
const view = usePivotView(props.preset)

const bucketItems = computed(() => VALID_BUCKETS.map((b) => ({ value: b, title: t(BUCKET_LABEL_KEYS[b]) })))
const groupingItems = computed(() => props.preset.groupings.map((g) => ({ value: g.value, title: t(g.labelKey) })))
const columnDefs = computed(() => [
  { field: 'bucket_start', headerName: t('pivot.cols.bucket') },
  { field: 'group_key', headerName: t('pivot.cols.group'),
    valueFormatter: (p: { value: unknown }) => groupLabel(p.value, t) },
  ...visibleColumns(props.preset, view.groupBy.value).map((c) => ({
    field: c.key, headerName: t(c.headerKey),
    valueFormatter: (p: { data: Record<string, unknown> }) => displayValue(p.data ?? {}, c),
  })),
])
const gridRows = computed(() => view.rows.value)

onMounted(view.refresh)
</script>
