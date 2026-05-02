<template>
  <div class="workflow-step-targets">
    <!-- Shift Targets Summary -->
    <v-card variant="outlined" class="mb-4">
      <v-card-title class="bg-grey-lighten-4 py-2">
        <v-icon class="mr-2" size="20">mdi-target</v-icon>
        {{ $t('workflow.shiftProductionTargets') }}
      </v-card-title>
      <v-card-text>
        <v-row>
          <v-col cols="6" md="3">
            <div class="text-center">
              <div class="text-h4 text-primary">{{ totalUnits }}</div>
              <div class="text-caption text-grey">{{ $t('workflow.totalUnits') }}</div>
            </div>
          </v-col>
          <v-col cols="6" md="3">
            <div class="text-center">
              <div class="text-h4 text-info">{{ workOrders.length }}</div>
              <div class="text-caption text-grey">{{ $t('workflow.workOrders') }}</div>
            </div>
          </v-col>
          <v-col cols="6" md="3">
            <div class="text-center">
              <div class="text-h4 text-success">{{ avgProgress }}%</div>
              <div class="text-caption text-grey">{{ $t('workflow.progress') }}</div>
            </div>
          </v-col>
          <v-col cols="6" md="3">
            <div class="text-center">
              <div class="text-h4 text-warning">{{ overdueCount }}</div>
              <div class="text-caption text-grey">{{ $t('workflow.overdue') }}</div>
            </div>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <!-- Work Orders Table (read-only review) -->
    <v-card variant="outlined" class="mb-4">
      <v-card-title class="d-flex align-center bg-grey-lighten-4 py-2">
        <v-icon class="mr-2" size="20">mdi-clipboard-list</v-icon>
        {{ $t('workflow.workOrdersForShift') }}
        <v-spacer />
        <v-btn
          size="small"
          color="primary"
          variant="elevated"
          :to="{ path: '/work-orders' }"
          target="_blank"
        >
          <v-icon start size="16">mdi-open-in-new</v-icon>
          {{ $t('workflow.openWorkOrders') }}
        </v-btn>
      </v-card-title>

      <v-card-text class="pa-0">
        <v-skeleton-loader v-if="loading" type="table-tbody" />
        <v-alert
          v-else-if="workOrders.length === 0"
          type="info"
          variant="tonal"
          class="ma-3"
        >
          {{ $t('workflow.noWorkOrdersForShift') }}
        </v-alert>
        <v-data-table
          v-else
          :headers="headers"
          :items="workOrders"
          :items-per-page="-1"
          :no-data-text="$t('common.noData')"
          density="compact"
          class="work-orders-table"
        >
          <template v-slot:item.dueDate="{ item }">
            <span :class="{ 'text-error': isOverdue(item.dueDate) }">
              {{ formatDate(item.dueDate) }}
            </span>
          </template>

          <template v-slot:item.progress="{ item }">
            <div class="d-flex align-center">
              <v-progress-linear
                :model-value="item.progress"
                :color="getProgressColor(item.progress)"
                height="8"
                rounded
                style="width: 80px"
                class="mr-2"
              />
              <span class="text-caption">{{ item.progress }}%</span>
            </div>
          </template>
        </v-data-table>
      </v-card-text>
    </v-card>

    <!-- Notes -->
    <v-textarea
      v-model="notes"
      :label="$t('workflow.shiftPlanningNotes')"
      :placeholder="$t('workflow.shiftPlanningPlaceholder')"
      variant="outlined"
      rows="3"
      class="mb-4"
      @update:model-value="emitUpdate"
    />

    <!-- Confirmation -->
    <v-checkbox
      v-model="confirmed"
      :label="$t('workflow.targetsConfirmLabel')"
      color="primary"
      @update:model-value="handleConfirm"
    />
  </div>
</template>

<script setup>
/**
 * WorkflowStepTargets — shift-start review checkpoint.
 *
 * Migrated 2026-05-01 from broken-endpoint mock-fallback pattern to a
 * canonical read-only checkpoint as part of Group G Surface #17 of the
 * entry-interface audit. The previous step targeted nonexistent
 * /work-orders/shift-queue and /materials/availability endpoints and
 * silently substituted hard-coded mock data. Same anti-pattern as the
 * Group B wizard steps; same option (c) treatment applied here.
 *
 * Now fetches the canonical GET /work-orders filtered by client and
 * (optionally) status, maps WorkOrderResponse fields to display
 * shape, and surfaces fetch errors via useNotificationStore. Materials
 * section removed (no backend representation today).
 */
import { ref, computed, onMounted } from 'vue'
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
const notes = ref('')
const workOrders = ref([])

const headers = computed(() => [
  { title: t('workflow.workOrder'), key: 'id', width: '140px' },
  { title: t('workflow.product'), key: 'product' },
  { title: t('common.target'), key: 'targetQuantity', width: '100px' },
  { title: t('workflow.completed'), key: 'completedQuantity', width: '110px' },
  { title: t('workflow.dueDate'), key: 'dueDate', width: '110px' },
  { title: t('workflow.progress'), key: 'progress', width: '160px' },
])

const totalUnits = computed(() =>
  workOrders.value.reduce(
    (sum, wo) => sum + Math.max(0, (wo.targetQuantity || 0) - (wo.completedQuantity || 0)),
    0,
  ),
)

const avgProgress = computed(() => {
  if (workOrders.value.length === 0) return 0
  const sum = workOrders.value.reduce((s, wo) => s + (wo.progress || 0), 0)
  return Math.round(sum / workOrders.value.length)
})

const overdueCount = computed(
  () => workOrders.value.filter((wo) => isOverdue(wo.dueDate)).length,
)

const getProgressColor = (progress) => {
  if (progress >= 80) return 'success'
  if (progress >= 50) return 'info'
  if (progress >= 25) return 'warning'
  return 'error'
}

const formatDate = (dateString) => {
  if (!dateString) return ''
  const date = new Date(dateString)
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

const isOverdue = (dateString) => {
  if (!dateString) return false
  const date = new Date(dateString)
  return date < new Date()
}

const emitUpdate = () => {
  emit('update', {
    workOrders: workOrders.value,
    totalUnits: totalUnits.value,
    avgProgress: avgProgress.value,
    notes: notes.value,
    isValid: confirmed.value,
  })
}

const handleConfirm = (value) => {
  if (value) {
    emit('complete', {
      workOrders: workOrders.value,
      totalUnits: totalUnits.value,
      notes: notes.value,
    })
  }
  emitUpdate()
}

const mapWorkOrder = (wo) => {
  const target = Number(wo.planned_quantity) || 0
  const completed = Number(wo.actual_quantity) || 0
  const progress = target > 0 ? Math.round((completed / target) * 100) : 0
  return {
    id: wo.work_order_id,
    product: wo.style_model || '',
    targetQuantity: target,
    completedQuantity: completed,
    dueDate: wo.planned_ship_date || wo.expected_date || wo.required_date || null,
    progress,
  }
}

const fetchData = async () => {
  loading.value = true
  try {
    const params = {}
    const clientId = authStore.user?.client_id_assigned ?? kpiStore.selectedClient
    if (clientId) params.client_id = clientId
    const response = await api.get('/work-orders', { params })
    workOrders.value = (response.data || []).map(mapWorkOrder)
    emitUpdate()
  } catch (error) {
    // eslint-disable-next-line no-console
    console.error('Failed to fetch work-orders for shift:', error)
    notificationStore.show({
      type: 'error',
      message: t('workflow.errors.loadWorkOrders'),
    })
    workOrders.value = []
    emitUpdate()
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.work-orders-table {
  border: none;
}

:deep(.v-data-table) {
  border-radius: 0;
}
</style>
