<template>
  <v-container fluid>
    <v-row>
      <v-col cols="12">
        <div class="d-flex align-center justify-space-between mb-4">
          <h1 class="text-h4">
            <v-icon class="mr-2">mdi-swap-horizontal</v-icon>
            {{ $t('admin.workflowConfig.title') }}
          </h1>
        </div>
        <p class="text-body-2 text-medium-emphasis mb-4">
          {{ $t('admin.workflowConfig.description') }}
        </p>
      </v-col>
    </v-row>

    <!-- Templates Overview Card -->
    <v-row class="mb-4">
      <v-col cols="12">
        <v-card>
          <v-card-title class="d-flex align-center">
            <v-icon class="mr-2" color="primary">mdi-file-document-multiple</v-icon>
            {{ $t('admin.workflowConfig.availableTemplates') }}
          </v-card-title>
          <v-card-text>
            <v-row>
              <v-col
                v-for="template in templates"
                :key="template.template_id"
                cols="12"
                md="4"
              >
                <v-card variant="outlined" class="h-100">
                  <v-card-title class="text-subtitle-1">
                    <v-icon class="mr-2" size="small" color="primary">mdi-clipboard-flow</v-icon>
                    {{ template.name }}
                  </v-card-title>
                  <v-card-text>
                    <p class="text-body-2 text-medium-emphasis mb-3">
                      {{ template.description }}
                    </p>
                    <div class="d-flex flex-wrap ga-1 mb-2">
                      <v-chip
                        v-for="status in template.workflow_statuses"
                        :key="status"
                        size="x-small"
                        :color="getStatusColor(status)"
                        variant="tonal"
                      >
                        {{ formatStatus(status) }}
                      </v-chip>
                    </div>
                    <div class="text-caption text-medium-emphasis">
                      <v-icon size="x-small" class="mr-1">mdi-archive</v-icon>
                      {{ $t('admin.workflowConfig.closureTrigger') }}: {{ formatClosureTrigger(template.workflow_closure_trigger) }}
                    </div>
                  </v-card-text>
                </v-card>
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Client Selector -->
    <v-row class="mb-4">
      <v-col cols="12" md="6">
        <v-autocomplete
          v-model="selectedClientId"
          :items="clients"
          item-title="client_name"
          item-value="client_id"
          :label="$t('admin.workflowConfig.selectClient')"
          prepend-inner-icon="mdi-domain"
          variant="outlined"
          density="comfortable"
          clearable
          :loading="loadingClients"
          @update:model-value="loadClientConfig"
        >
          <template v-slot:item="{ item, props }">
            <v-list-item v-bind="props">
              <template v-slot:prepend>
                <v-icon>mdi-domain</v-icon>
              </template>
              <v-list-item-subtitle>ID: {{ item.raw.client_id }}</v-list-item-subtitle>
            </v-list-item>
          </template>
        </v-autocomplete>
      </v-col>
      <v-col cols="12" md="6" class="d-flex align-center ga-2">
        <v-btn
          color="primary"
          :disabled="!selectedClientId"
          @click="openEditDialog"
        >
          <v-icon left>mdi-pencil</v-icon>
          {{ $t('common.edit') }}
        </v-btn>
        <v-menu v-if="selectedClientId">
          <template v-slot:activator="{ props }">
            <v-btn
              v-bind="props"
              color="secondary"
              variant="outlined"
            >
              <v-icon left>mdi-file-import</v-icon>
              {{ $t('admin.workflowConfig.applyTemplate') }}
            </v-btn>
          </template>
          <v-list density="compact">
            <v-list-subheader>{{ $t('admin.workflowConfig.selectTemplate') }}</v-list-subheader>
            <v-list-item
              v-for="template in templates"
              :key="template.template_id"
              @click="confirmApplyTemplate(template)"
            >
              <template v-slot:prepend>
                <v-icon>mdi-clipboard-flow</v-icon>
              </template>
              <v-list-item-title>{{ template.name }}</v-list-item-title>
              <v-list-item-subtitle>{{ template.description }}</v-list-item-subtitle>
            </v-list-item>
          </v-list>
        </v-menu>
      </v-col>
    </v-row>

    <!-- Client Workflow Config Display -->
    <v-row v-if="selectedClientId">
      <v-col cols="12">
        <v-card :loading="loadingConfig">
          <v-card-title class="d-flex align-center">
            <v-icon class="mr-2" color="primary">mdi-cog-sync</v-icon>
            {{ $t('admin.workflowConfig.configFor') }}: {{ selectedClientName }}
            <v-spacer />
            <v-chip color="info" size="small">
              v{{ workflowConfig?.workflow_version || 1 }}
            </v-chip>
          </v-card-title>

          <v-card-text v-if="workflowConfig">
            <!-- Workflow Statuses -->
            <h3 class="text-subtitle-1 font-weight-bold mb-3">
              <v-icon class="mr-1" size="small">mdi-format-list-numbered</v-icon>
              {{ $t('admin.workflowConfig.workflowStatuses') }}
            </h3>
            <div class="workflow-pipeline mb-4">
              <div
                v-for="(status, index) in workflowConfig.workflow_statuses"
                :key="status"
                class="d-inline-flex align-center"
              >
                <v-chip
                  :color="getStatusColor(status)"
                  variant="flat"
                  size="small"
                >
                  {{ formatStatus(status) }}
                </v-chip>
                <v-icon
                  v-if="index < workflowConfig.workflow_statuses.length - 1"
                  class="mx-1"
                  size="small"
                  color="grey"
                >
                  mdi-arrow-right
                </v-icon>
              </div>
            </div>

            <!-- Optional Statuses -->
            <div v-if="workflowConfig.workflow_optional_statuses?.length" class="mb-4">
              <span class="text-caption text-medium-emphasis mr-2">
                {{ $t('admin.workflowConfig.optionalStatuses') }}:
              </span>
              <v-chip
                v-for="status in workflowConfig.workflow_optional_statuses"
                :key="status"
                size="x-small"
                variant="outlined"
                color="grey"
                class="mr-1"
              >
                {{ formatStatus(status) }}
              </v-chip>
            </div>

            <v-divider class="my-4" />

            <!-- Closure Trigger -->
            <h3 class="text-subtitle-1 font-weight-bold mb-3">
              <v-icon class="mr-1" size="small">mdi-archive</v-icon>
              {{ $t('admin.workflowConfig.closureTrigger') }}
            </h3>
            <v-chip color="purple" variant="tonal" class="mb-4">
              <v-icon size="small" class="mr-1">{{ getClosureTriggerIcon(workflowConfig.workflow_closure_trigger) }}</v-icon>
              {{ formatClosureTrigger(workflowConfig.workflow_closure_trigger) }}
            </v-chip>

            <v-divider class="my-4" />

            <!-- Transition Rules -->
            <h3 class="text-subtitle-1 font-weight-bold mb-3">
              <v-icon class="mr-1" size="small">mdi-transit-connection-variant</v-icon>
              {{ $t('admin.workflowConfig.transitionRules') }}
            </h3>
            <v-table density="compact" class="transition-table">
              <thead>
                <tr>
                  <th>{{ $t('admin.workflowConfig.toStatus') }}</th>
                  <th>{{ $t('admin.workflowConfig.allowedFromStatuses') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(fromStatuses, toStatus) in workflowConfig.workflow_transitions" :key="toStatus">
                  <td>
                    <v-chip :color="getStatusColor(toStatus)" size="small" variant="flat">
                      {{ formatStatus(toStatus) }}
                    </v-chip>
                  </td>
                  <td>
                    <v-chip
                      v-for="fromStatus in fromStatuses"
                      :key="fromStatus"
                      :color="getStatusColor(fromStatus)"
                      size="x-small"
                      variant="tonal"
                      class="mr-1 mb-1"
                    >
                      {{ formatStatus(fromStatus) }}
                    </v-chip>
                  </td>
                </tr>
              </tbody>
            </v-table>
          </v-card-text>

          <v-card-text v-else-if="!loadingConfig">
            <v-alert type="info" variant="tonal">
              {{ $t('admin.workflowConfig.selectClientPrompt') }}
            </v-alert>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Workflow Analytics -->
    <v-row v-if="selectedClientId && workflowConfig" class="mt-4">
      <v-col cols="12" md="6">
        <v-card>
          <v-card-title>
            <v-icon class="mr-2" size="small">mdi-chart-pie</v-icon>
            {{ $t('admin.workflowConfig.statusDistribution') }}
          </v-card-title>
          <v-card-text>
            <div v-if="loadingAnalytics" class="text-center py-4">
              <v-progress-circular indeterminate size="32" />
            </div>
            <div v-else-if="statusDistribution">
              <div
                v-for="item in statusDistribution.by_status"
                :key="item.status"
                class="d-flex align-center justify-space-between mb-2"
              >
                <v-chip :color="getStatusColor(item.status)" size="small" variant="tonal">
                  {{ formatStatus(item.status) }}
                </v-chip>
                <div class="d-flex align-center">
                  <v-progress-linear
                    :model-value="item.percentage"
                    :color="getStatusColor(item.status)"
                    height="8"
                    rounded
                    style="width: 100px;"
                    class="mr-2"
                  />
                  <span class="text-body-2 font-weight-medium" style="min-width: 80px;">
                    {{ item.count }} ({{ item.percentage.toFixed(1) }}%)
                  </span>
                </div>
              </div>
              <v-divider class="my-3" />
              <div class="text-body-2 text-medium-emphasis">
                {{ $t('admin.workflowConfig.totalOrders') }}: <strong>{{ statusDistribution.total_work_orders }}</strong>
              </div>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="6">
        <v-card>
          <v-card-title>
            <v-icon class="mr-2" size="small">mdi-clock-fast</v-icon>
            {{ $t('admin.workflowConfig.averageTimes') }}
          </v-card-title>
          <v-card-text>
            <div v-if="loadingAnalytics" class="text-center py-4">
              <v-progress-circular indeterminate size="32" />
            </div>
            <div v-else-if="averageTimes">
              <v-list density="compact" class="bg-transparent">
                <v-list-item v-if="averageTimes.averages?.lifecycle_days != null">
                  <template v-slot:prepend>
                    <v-icon size="small" color="primary">mdi-calendar-range</v-icon>
                  </template>
                  <v-list-item-title>{{ $t('admin.workflowConfig.avgLifecycle') }}</v-list-item-title>
                  <template v-slot:append>
                    <span class="font-weight-bold">{{ averageTimes.averages.lifecycle_days.toFixed(1) }} {{ $t('common.days') }}</span>
                  </template>
                </v-list-item>
                <v-list-item v-if="averageTimes.averages?.lead_time_hours != null">
                  <template v-slot:prepend>
                    <v-icon size="small" color="info">mdi-inbox</v-icon>
                  </template>
                  <v-list-item-title>{{ $t('admin.workflowConfig.avgLeadTime') }}</v-list-item-title>
                  <template v-slot:append>
                    <span class="font-weight-bold">{{ averageTimes.averages.lead_time_hours.toFixed(1) }} {{ $t('common.hours') }}</span>
                  </template>
                </v-list-item>
                <v-list-item v-if="averageTimes.averages?.processing_time_hours != null">
                  <template v-slot:prepend>
                    <v-icon size="small" color="success">mdi-factory</v-icon>
                  </template>
                  <v-list-item-title>{{ $t('admin.workflowConfig.avgProcessing') }}</v-list-item-title>
                  <template v-slot:append>
                    <span class="font-weight-bold">{{ averageTimes.averages.processing_time_hours.toFixed(1) }} {{ $t('common.hours') }}</span>
                  </template>
                </v-list-item>
              </v-list>
              <v-divider class="my-3" />
              <div class="text-body-2 text-medium-emphasis">
                {{ $t('admin.workflowConfig.sampleSize') }}: <strong>{{ averageTimes.count }}</strong>
              </div>
            </div>
            <v-alert v-else type="info" variant="tonal" density="compact">
              {{ $t('admin.workflowConfig.noAnalyticsData') }}
            </v-alert>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Edit Dialog -->
    <v-dialog v-model="editDialog" max-width="900" persistent scrollable>
      <v-card>
        <v-card-title>
          <v-icon class="mr-2">mdi-pencil</v-icon>
          {{ $t('admin.workflowConfig.editConfig') }}: {{ selectedClientName }}
        </v-card-title>
        <v-card-text style="max-height: 70vh;">
          <v-form ref="configForm" v-model="formValid">
            <!-- Workflow Statuses -->
            <h3 class="text-subtitle-1 font-weight-bold mb-3">
              {{ $t('admin.workflowConfig.workflowStatuses') }}
            </h3>
            <v-alert type="info" variant="tonal" density="compact" class="mb-3">
              {{ $t('admin.workflowConfig.statusOrderHint') }}
            </v-alert>
            <v-chip-group
              v-model="formData.workflow_statuses"
              multiple
              column
              class="mb-4"
            >
              <v-chip
                v-for="status in allStatuses"
                :key="status"
                :value="status"
                :color="getStatusColor(status)"
                filter
                variant="outlined"
              >
                {{ formatStatus(status) }}
              </v-chip>
            </v-chip-group>

            <v-divider class="my-4" />

            <!-- Optional Statuses -->
            <h3 class="text-subtitle-1 font-weight-bold mb-3">
              {{ $t('admin.workflowConfig.optionalStatuses') }}
            </h3>
            <v-alert type="info" variant="tonal" density="compact" class="mb-3">
              {{ $t('admin.workflowConfig.optionalHint') }}
            </v-alert>
            <v-chip-group
              v-model="formData.workflow_optional_statuses"
              multiple
              column
              class="mb-4"
            >
              <v-chip
                v-for="status in formData.workflow_statuses"
                :key="status"
                :value="status"
                color="grey"
                filter
                variant="outlined"
              >
                {{ formatStatus(status) }}
              </v-chip>
            </v-chip-group>

            <v-divider class="my-4" />

            <!-- Closure Trigger -->
            <h3 class="text-subtitle-1 font-weight-bold mb-3">
              {{ $t('admin.workflowConfig.closureTrigger') }}
            </h3>
            <v-select
              v-model="formData.workflow_closure_trigger"
              :items="closureTriggerOptions"
              item-title="title"
              item-value="value"
              variant="outlined"
              density="comfortable"
              :hint="getClosureTriggerHint(formData.workflow_closure_trigger)"
              persistent-hint
            />

            <v-divider class="my-4" />

            <!-- Transition Rules Editor -->
            <h3 class="text-subtitle-1 font-weight-bold mb-3">
              {{ $t('admin.workflowConfig.transitionRules') }}
            </h3>
            <v-alert type="info" variant="tonal" density="compact" class="mb-3">
              {{ $t('admin.workflowConfig.transitionHint') }}
            </v-alert>
            <v-expansion-panels variant="accordion" class="mb-4">
              <v-expansion-panel
                v-for="status in formData.workflow_statuses"
                :key="status"
              >
                <v-expansion-panel-title>
                  <v-chip :color="getStatusColor(status)" size="small" variant="flat" class="mr-2">
                    {{ formatStatus(status) }}
                  </v-chip>
                  <span class="text-body-2">
                    {{ $t('admin.workflowConfig.allowedFrom') }}:
                    {{ (formData.workflow_transitions[status] || []).length }} {{ $t('admin.workflowConfig.statuses') }}
                  </span>
                </v-expansion-panel-title>
                <v-expansion-panel-text>
                  <v-chip-group
                    v-model="formData.workflow_transitions[status]"
                    multiple
                    column
                  >
                    <v-chip
                      v-for="fromStatus in allStatuses.filter(s => s !== status)"
                      :key="fromStatus"
                      :value="fromStatus"
                      :color="getStatusColor(fromStatus)"
                      filter
                      variant="outlined"
                      size="small"
                    >
                      {{ formatStatus(fromStatus) }}
                    </v-chip>
                  </v-chip-group>
                </v-expansion-panel-text>
              </v-expansion-panel>
            </v-expansion-panels>
          </v-form>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="editDialog = false">{{ $t('common.cancel') }}</v-btn>
          <v-btn color="primary" :loading="saving" @click="saveConfig">
            {{ $t('common.save') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Confirm Apply Template Dialog -->
    <v-dialog v-model="confirmTemplateDialog" max-width="500">
      <v-card>
        <v-card-title class="text-warning">
          <v-icon class="mr-2" color="warning">mdi-alert</v-icon>
          {{ $t('admin.workflowConfig.confirmApplyTemplate') }}
        </v-card-title>
        <v-card-text>
          <p class="mb-3">
            {{ $t('admin.workflowConfig.confirmApplyMessage', {
              template: selectedTemplate?.name,
              client: selectedClientName
            }) }}
          </p>
          <v-alert type="warning" variant="tonal" density="compact">
            {{ $t('admin.workflowConfig.templateWarning') }}
          </v-alert>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="confirmTemplateDialog = false">{{ $t('common.cancel') }}</v-btn>
          <v-btn color="warning" :loading="applyingTemplate" @click="applyTemplate">
            {{ $t('admin.workflowConfig.apply') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Snackbar -->
    <v-snackbar v-model="snackbar.show" :color="snackbar.color" :timeout="3000">
      {{ snackbar.text }}
    </v-snackbar>
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/services/api'
import {
  getWorkflowConfig,
  updateWorkflowConfig,
  applyWorkflowTemplate,
  getWorkflowTemplates,
  getStatusDistribution,
  getClientAverageTimes
} from '@/services/api/workflow'

const { t } = useI18n()

// All possible statuses
const allStatuses = [
  'RECEIVED', 'RELEASED', 'DEMOTED', 'ACTIVE', 'IN_PROGRESS',
  'ON_HOLD', 'COMPLETED', 'SHIPPED', 'CLOSED', 'REJECTED', 'CANCELLED'
]

// State
const loadingClients = ref(false)
const loadingConfig = ref(false)
const loadingAnalytics = ref(false)
const saving = ref(false)
const applyingTemplate = ref(false)

const clients = ref([])
const selectedClientId = ref(null)
const workflowConfig = ref(null)
const templates = ref([])
const statusDistribution = ref(null)
const averageTimes = ref(null)

const editDialog = ref(false)
const confirmTemplateDialog = ref(false)
const selectedTemplate = ref(null)
const formValid = ref(true)
const configForm = ref(null)

const snackbar = ref({ show: false, text: '', color: 'success' })

// Form data
const formData = ref({
  workflow_statuses: [],
  workflow_transitions: {},
  workflow_optional_statuses: [],
  workflow_closure_trigger: 'at_shipment'
})

// Closure trigger options
const closureTriggerOptions = [
  { title: t('admin.workflowConfig.closureTriggers.atShipment'), value: 'at_shipment' },
  { title: t('admin.workflowConfig.closureTriggers.atClientReceipt'), value: 'at_client_receipt' },
  { title: t('admin.workflowConfig.closureTriggers.atCompletion'), value: 'at_completion' },
  { title: t('admin.workflowConfig.closureTriggers.manual'), value: 'manual' }
]

// Computed
const selectedClientName = computed(() => {
  const client = clients.value.find(c => c.client_id === selectedClientId.value)
  return client?.client_name || selectedClientId.value
})

// Methods
const getStatusColor = (status) => {
  const colors = {
    RECEIVED: 'blue-grey',
    RELEASED: 'cyan',
    DEMOTED: 'orange',
    ACTIVE: 'info',
    IN_PROGRESS: 'indigo',
    ON_HOLD: 'warning',
    COMPLETED: 'success',
    SHIPPED: 'purple',
    CLOSED: 'grey',
    REJECTED: 'error',
    CANCELLED: 'grey-darken-1'
  }
  return colors[status] || 'grey'
}

const formatStatus = (status) => {
  const labels = {
    RECEIVED: t('workflow.status.received'),
    RELEASED: t('workflow.status.released'),
    DEMOTED: t('workflow.status.demoted'),
    ACTIVE: t('workflow.status.active'),
    IN_PROGRESS: t('workflow.status.in_wip'),
    ON_HOLD: t('workflow.status.on_hold'),
    COMPLETED: t('workflow.status.completed'),
    SHIPPED: t('workflow.status.shipped'),
    CLOSED: t('workflow.status.closed'),
    REJECTED: t('workflow.status.rejected'),
    CANCELLED: t('workflow.status.cancelled')
  }
  return labels[status] || status
}

const formatClosureTrigger = (trigger) => {
  const labels = {
    at_shipment: t('admin.workflowConfig.closureTriggers.atShipment'),
    at_client_receipt: t('admin.workflowConfig.closureTriggers.atClientReceipt'),
    at_completion: t('admin.workflowConfig.closureTriggers.atCompletion'),
    manual: t('admin.workflowConfig.closureTriggers.manual')
  }
  return labels[trigger] || trigger
}

const getClosureTriggerIcon = (trigger) => {
  const icons = {
    at_shipment: 'mdi-truck-delivery',
    at_client_receipt: 'mdi-package-variant-closed-check',
    at_completion: 'mdi-check-circle',
    manual: 'mdi-hand-pointing-right'
  }
  return icons[trigger] || 'mdi-help-circle'
}

const getClosureTriggerHint = (trigger) => {
  const hints = {
    at_shipment: t('admin.workflowConfig.closureHints.atShipment'),
    at_client_receipt: t('admin.workflowConfig.closureHints.atClientReceipt'),
    at_completion: t('admin.workflowConfig.closureHints.atCompletion'),
    manual: t('admin.workflowConfig.closureHints.manual')
  }
  return hints[trigger] || ''
}

const loadClients = async () => {
  loadingClients.value = true
  try {
    const response = await api.get('/clients')
    clients.value = response.data
  } catch (error) {
    console.error('Failed to load clients:', error)
    showSnackbar(t('admin.workflowConfig.errors.loadClients'), 'error')
  } finally {
    loadingClients.value = false
  }
}

const loadTemplates = async () => {
  try {
    const response = await getWorkflowTemplates()
    templates.value = response.data.templates || []
  } catch (error) {
    console.error('Failed to load templates:', error)
  }
}

const loadClientConfig = async () => {
  if (!selectedClientId.value) {
    workflowConfig.value = null
    statusDistribution.value = null
    averageTimes.value = null
    return
  }

  loadingConfig.value = true
  try {
    const response = await getWorkflowConfig(selectedClientId.value)
    workflowConfig.value = response.data
    await loadAnalytics()
  } catch (error) {
    console.error('Failed to load workflow config:', error)
    showSnackbar(t('admin.workflowConfig.errors.loadConfig'), 'error')
  } finally {
    loadingConfig.value = false
  }
}

const loadAnalytics = async () => {
  if (!selectedClientId.value) return

  loadingAnalytics.value = true
  try {
    const [distResponse, timesResponse] = await Promise.all([
      getStatusDistribution(selectedClientId.value),
      getClientAverageTimes(selectedClientId.value)
    ])
    statusDistribution.value = distResponse.data
    averageTimes.value = timesResponse.data
  } catch (error) {
    console.error('Failed to load analytics:', error)
    statusDistribution.value = null
    averageTimes.value = null
  } finally {
    loadingAnalytics.value = false
  }
}

const openEditDialog = () => {
  if (workflowConfig.value) {
    formData.value = {
      workflow_statuses: [...(workflowConfig.value.workflow_statuses || [])],
      workflow_transitions: JSON.parse(JSON.stringify(workflowConfig.value.workflow_transitions || {})),
      workflow_optional_statuses: [...(workflowConfig.value.workflow_optional_statuses || [])],
      workflow_closure_trigger: workflowConfig.value.workflow_closure_trigger || 'at_shipment'
    }
  }
  editDialog.value = true
}

const saveConfig = async () => {
  saving.value = true
  try {
    await updateWorkflowConfig(selectedClientId.value, {
      workflow_statuses: formData.value.workflow_statuses,
      workflow_transitions: formData.value.workflow_transitions,
      workflow_optional_statuses: formData.value.workflow_optional_statuses,
      workflow_closure_trigger: formData.value.workflow_closure_trigger
    })
    showSnackbar(t('admin.workflowConfig.success.updated'), 'success')
    editDialog.value = false
    await loadClientConfig()
  } catch (error) {
    console.error('Failed to save config:', error)
    showSnackbar(error.response?.data?.detail || t('admin.workflowConfig.errors.save'), 'error')
  } finally {
    saving.value = false
  }
}

const confirmApplyTemplate = (template) => {
  selectedTemplate.value = template
  confirmTemplateDialog.value = true
}

const applyTemplate = async () => {
  if (!selectedTemplate.value) return

  applyingTemplate.value = true
  try {
    await applyWorkflowTemplate(selectedClientId.value, selectedTemplate.value.template_id)
    showSnackbar(t('admin.workflowConfig.success.templateApplied'), 'success')
    confirmTemplateDialog.value = false
    await loadClientConfig()
  } catch (error) {
    console.error('Failed to apply template:', error)
    showSnackbar(error.response?.data?.detail || t('admin.workflowConfig.errors.applyTemplate'), 'error')
  } finally {
    applyingTemplate.value = false
  }
}

const showSnackbar = (text, color) => {
  snackbar.value = { show: true, text, color }
}

// Lifecycle
onMounted(async () => {
  await Promise.all([loadClients(), loadTemplates()])
  // Auto-select first client to show default workflow
  if (clients.value.length > 0 && !selectedClientId.value) {
    selectedClientId.value = clients.value[0].client_id
    await loadClientConfig()
  }
})
</script>

<style scoped>
.workflow-pipeline {
  overflow-x: auto;
  white-space: nowrap;
  padding: 8px 0;
}

.transition-table {
  background: transparent;
}

.transition-table th {
  font-weight: 600 !important;
}
</style>
