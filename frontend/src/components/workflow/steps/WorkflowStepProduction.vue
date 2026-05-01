<template>
  <div class="workflow-step-production">
    <!-- Production Summary -->
    <v-row class="mb-4">
      <v-col cols="6" md="3">
        <v-card variant="outlined" class="text-center pa-3">
          <div class="text-h4 text-primary">{{ totalProduced }}</div>
          <div class="text-caption text-grey">{{ $t('workflow.unitsProduced') }}</div>
        </v-card>
      </v-col>
      <v-col cols="6" md="3">
        <v-card variant="outlined" class="text-center pa-3">
          <div class="text-h4 text-error">{{ totalDefects }}</div>
          <div class="text-caption text-grey">{{ $t('workflow.totalDefects') }}</div>
        </v-card>
      </v-col>
      <v-col cols="6" md="3">
        <v-card variant="outlined" class="text-center pa-3">
          <div class="text-h4 text-info">{{ workOrdersCount }}</div>
          <div class="text-caption text-grey">{{ $t('workflow.workOrdersCovered') }}</div>
        </v-card>
      </v-col>
      <v-col cols="6" md="3">
        <v-card variant="outlined" class="text-center pa-3">
          <div class="text-h4" :class="entries.length > 0 ? 'text-success' : 'text-grey'">
            {{ entries.length }}
          </div>
          <div class="text-caption text-grey">{{ $t('workflow.entriesRecorded') }}</div>
        </v-card>
      </v-col>
    </v-row>

    <!-- Today's Entries (read-only — link out to grid for entry) -->
    <v-card variant="outlined" class="mb-4">
      <v-card-title class="d-flex align-center bg-grey-lighten-4 py-2">
        <v-icon class="mr-2" size="20">mdi-clipboard-list</v-icon>
        {{ $t('workflow.workOrdersFinalCount') }}
        <v-spacer />
        <v-btn
          size="small"
          color="primary"
          variant="elevated"
          :to="{ path: '/production-entry' }"
          target="_blank"
        >
          <v-icon start size="16">mdi-open-in-new</v-icon>
          {{ $t('workflow.openProductionGrid') }}
        </v-btn>
      </v-card-title>

      <v-card-text class="pa-0">
        <v-skeleton-loader v-if="loading" type="table-tbody" />
        <v-alert
          v-else-if="entries.length === 0"
          type="warning"
          variant="tonal"
          class="ma-3"
        >
          {{ $t('workflow.noProductionEntries') }}
        </v-alert>
        <v-data-table
          v-else
          :headers="headers"
          :items="byWorkOrder"
          :items-per-page="-1"
          :no-data-text="$t('common.noData')"
          density="compact"
        >
          <template v-slot:item.units_produced="{ item }">
            <span class="font-weight-medium">{{ item.units_produced }}</span>
          </template>
          <template v-slot:item.defect_count="{ item }">
            <v-chip
              v-if="item.defect_count > 0"
              size="x-small"
              color="error"
              variant="tonal"
            >
              {{ item.defect_count }}
            </v-chip>
            <span v-else class="text-grey">0</span>
          </template>
          <template v-slot:item.entry_count="{ item }">
            <v-chip size="x-small" variant="flat" color="success">
              {{ item.entry_count }}
            </v-chip>
          </template>
        </v-data-table>
      </v-card-text>
    </v-card>

    <!-- Confirmation -->
    <v-checkbox
      v-model="confirmed"
      :disabled="!canConfirm"
      :label="$t('workflow.productionConfirmLabel')"
      color="primary"
      @update:model-value="handleConfirm"
    />

    <v-alert
      v-if="entries.length === 0"
      type="warning"
      variant="tonal"
      density="compact"
      class="mt-2"
    >
      {{ $t('workflow.productionNoEntriesAlert') }}
    </v-alert>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { format } from 'date-fns'
import { useI18n } from 'vue-i18n'
import api from '@/services/api'
import { useAuthStore } from '@/stores/authStore'
import { useKPIStore } from '@/stores/kpi'
import { useNotificationStore } from '@/stores/notificationStore'

const { t } = useI18n()
const emit = defineEmits(['complete', 'update'])

const authStore = useAuthStore()
const kpiStore = useKPIStore()
const notificationStore = useNotificationStore()

const loading = ref(true)
const confirmed = ref(false)
const entries = ref([])

const headers = computed(() => [
  { title: t('workflow.workOrder'), key: 'work_order_id', width: '180px' },
  { title: t('workflow.entriesRecorded'), key: 'entry_count', width: '120px' },
  { title: t('workflow.unitsProduced'), key: 'units_produced', width: '140px' },
  { title: t('grids.columns.defectQty'), key: 'defect_count', width: '110px' },
])

const totalProduced = computed(() =>
  entries.value.reduce((sum, e) => sum + (e.units_produced || 0), 0),
)

const totalDefects = computed(() =>
  entries.value.reduce((sum, e) => sum + (e.defect_count || 0), 0),
)

// Group entries by work_order_id for the summary table.
const byWorkOrder = computed(() => {
  const buckets = new Map()
  entries.value.forEach((e) => {
    const key = e.work_order_id || '—'
    if (!buckets.has(key)) {
      buckets.set(key, {
        work_order_id: key,
        entry_count: 0,
        units_produced: 0,
        defect_count: 0,
      })
    }
    const row = buckets.get(key)
    row.entry_count += 1
    row.units_produced += e.units_produced || 0
    row.defect_count += e.defect_count || 0
  })
  return [...buckets.values()].sort((a, b) =>
    String(a.work_order_id).localeCompare(String(b.work_order_id)),
  )
})

const workOrdersCount = computed(() => byWorkOrder.value.length)

// Operator can confirm only when at least one entry exists for today.
// The wizard's role is to verify completeness, not to be an entry surface.
const canConfirm = computed(() => entries.value.length > 0)

const emitUpdate = () => {
  emit('update', {
    entries: entries.value,
    totalProduced: totalProduced.value,
    totalDefects: totalDefects.value,
    workOrdersCount: workOrdersCount.value,
    isValid: confirmed.value && canConfirm.value,
  })
}

const handleConfirm = (value) => {
  if (value && canConfirm.value) {
    emit('complete', {
      entries: entries.value,
      totalProduced: totalProduced.value,
      totalDefects: totalDefects.value,
      workOrdersCount: workOrdersCount.value,
    })
  }
  emitUpdate()
}

const fetchData = async () => {
  loading.value = true
  try {
    const today = format(new Date(), 'yyyy-MM-dd')
    const params = { start_date: today, end_date: today }
    const clientId = authStore.user?.client_id_assigned ?? kpiStore.selectedClient
    if (clientId) params.client_id = clientId
    const response = await api.get('/production', { params })
    entries.value = response.data || []
    emitUpdate()
  } catch (error) {
    // eslint-disable-next-line no-console
    console.error('Failed to fetch production data:', error)
    notificationStore.show({
      type: 'error',
      message: t('workflow.errors.loadProduction'),
    })
    entries.value = []
    emitUpdate()
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped></style>
