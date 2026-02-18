<template>
  <v-container fluid>
    <v-row>
      <v-col cols="12">
        <h1 class="text-h4 mb-2">
          <v-icon class="mr-2">mdi-swap-horizontal</v-icon>
          {{ $t('admin.workflowConfig.title') }}
        </h1>
        <p class="text-body-2 text-medium-emphasis mb-4">{{ $t('admin.workflowConfig.description') }}</p>
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
    <WorkflowAnalyticsCards
      v-if="selectedClientId && workflowConfig"
      :loading="loadingAnalytics"
      :status-distribution="statusDistribution"
      :average-times="averageTimes"
      :get-status-color="getStatusColor"
      :format-status="formatStatus"
    />
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
import { onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import useWorkflowConfigData from '@/composables/useWorkflowConfigData'
import useWorkflowConfigForms from '@/composables/useWorkflowConfigForms'
import WorkflowAnalyticsCards from './components/WorkflowAnalyticsCards.vue'

const { t } = useI18n()

// Data composable
const {
  loadingClients,
  loadingConfig,
  loadingAnalytics,
  clients,
  selectedClientId,
  workflowConfig,
  templates,
  statusDistribution,
  averageTimes,
  allStatuses,
  closureTriggerOptions,
  selectedClientName,
  getStatusColor,
  formatStatus,
  formatClosureTrigger,
  getClosureTriggerIcon,
  getClosureTriggerHint,
  loadClients,
  loadTemplates,
  loadClientConfig
} = useWorkflowConfigData()

// Forms composable
const {
  editDialog,
  confirmTemplateDialog,
  selectedTemplate,
  formValid,
  configForm,
  saving,
  applyingTemplate,
  formData,
  snackbar,
  showSnackbar,
  openEditDialog,
  saveConfig,
  confirmApplyTemplate,
  applyTemplate
} = useWorkflowConfigForms(selectedClientId, workflowConfig, loadClientConfig)

// Lifecycle — wrap loadClientConfig to route errors to snackbar
const loadClientConfigSafe = async () => {
  try {
    await loadClientConfig()
  } catch {
    showSnackbar(t('admin.workflowConfig.errors.loadConfig'), 'error')
  }
}

onMounted(async () => {
  try {
    await Promise.all([loadClients(), loadTemplates()])
  } catch {
    showSnackbar(t('admin.workflowConfig.errors.loadClients'), 'error')
  }
  if (clients.value.length > 0 && !selectedClientId.value) {
    selectedClientId.value = clients.value[0].client_id
    await loadClientConfigSafe()
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
