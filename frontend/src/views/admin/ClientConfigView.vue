<template>
  <v-container fluid>
    <v-row>
      <v-col cols="12">
        <div class="d-flex align-center justify-space-between mb-4">
          <h1 class="text-h4">
            <v-icon class="mr-2">mdi-cog-outline</v-icon>
            {{ $t('admin.clientConfig.title') }}
          </h1>
        </div>
        <p class="text-body-2 text-medium-emphasis mb-4">
          {{ $t('admin.clientConfig.description') }}
        </p>
      </v-col>
    </v-row>

    <!-- Global Defaults Card -->
    <v-row class="mb-4">
      <v-col cols="12">
        <v-card>
          <v-card-title class="d-flex align-center">
            <v-icon class="mr-2" color="info">mdi-earth</v-icon>
            {{ $t('admin.clientConfig.globalDefaults') }}
            <v-spacer />
            <v-chip color="info" size="small">
              {{ $t('admin.clientConfig.systemDefaults') }}
            </v-chip>
          </v-card-title>
          <v-card-text v-if="globalDefaults">
            <v-row>
              <v-col cols="12" md="4" v-for="(value, key) in globalDefaults" :key="key">
                <div class="d-flex justify-space-between align-center pa-2 bg-grey-lighten-4 rounded">
                  <span class="text-body-2 font-weight-medium">{{ formatLabel(key) }}</span>
                  <v-chip size="small" color="grey">{{ formatValue(key, value) }}</v-chip>
                </div>
              </v-col>
            </v-row>
          </v-card-text>
          <v-card-text v-else>
            <v-progress-circular indeterminate size="24" />
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
          :label="$t('admin.clientConfig.selectClient')"
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
      <v-col cols="12" md="6" class="d-flex align-center">
        <v-btn
          color="primary"
          :disabled="!selectedClientId"
          @click="openEditDialog"
          class="mr-2"
        >
          <v-icon left>mdi-pencil</v-icon>
          {{ clientConfig && !clientConfig.is_default ? $t('common.edit') : $t('admin.clientConfig.createConfig') }}
        </v-btn>
        <v-btn
          v-if="clientConfig && !clientConfig.is_default"
          color="warning"
          variant="outlined"
          @click="confirmResetToDefaults"
        >
          <v-icon left>mdi-restore</v-icon>
          {{ $t('admin.clientConfig.resetToDefaults') }}
        </v-btn>
      </v-col>
    </v-row>

    <!-- Client Config Display -->
    <v-row v-if="selectedClientId">
      <v-col cols="12">
        <v-card :loading="loadingConfig">
          <v-card-title class="d-flex align-center">
            <v-icon class="mr-2" :color="clientConfig?.is_default ? 'grey' : 'success'">
              {{ clientConfig?.is_default ? 'mdi-cog' : 'mdi-cog-sync' }}
            </v-icon>
            {{ $t('admin.clientConfig.configFor') }}: {{ selectedClientName }}
            <v-spacer />
            <v-chip :color="clientConfig?.is_default ? 'grey' : 'success'" size="small">
              {{ clientConfig?.is_default ? $t('admin.clientConfig.usingDefaults') : $t('admin.clientConfig.customConfig') }}
            </v-chip>
          </v-card-title>

          <v-card-text v-if="clientConfig">
            <template v-for="section in configSections" :key="section.key">
              <h3 class="text-subtitle-1 font-weight-bold mb-3">
                <v-icon class="mr-1" size="small">{{ section.icon }}</v-icon>
                {{ $t(section.titleKey) }}
              </h3>
              <v-row class="mb-4">
                <v-col v-for="field in section.fields" :key="field.configKey" cols="12" md="4">
                  <ConfigValueCard
                    :label="$t(field.labelKey)"
                    :value="field.getValue(clientConfig, globalDefaults)"
                    :is-default="field.getIsDefault ? field.getIsDefault(clientConfig) : clientConfig.is_default"
                  />
                </v-col>
              </v-row>
            </template>
          </v-card-text>

          <v-card-text v-else-if="!loadingConfig">
            <v-alert type="info" variant="tonal">
              {{ $t('admin.clientConfig.selectClientPrompt') }}
            </v-alert>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Edit Dialog -->
    <v-dialog v-model="editDialog" max-width="800" persistent>
      <v-card>
        <v-card-title>
          <v-icon class="mr-2">mdi-pencil</v-icon>
          {{ $t('admin.clientConfig.editConfig') }}: {{ selectedClientName }}
        </v-card-title>
        <v-card-text>
          <v-form ref="configForm" v-model="formValid">
            <v-row>
              <v-col v-for="field in editFormFields" :key="field.key" cols="12" :md="field.md || 6">
                <v-select
                  v-if="field.type === 'select'"
                  v-model="formData[field.key]"
                  :items="field.items"
                  :label="$t(field.labelKey)"
                  :prepend-icon="field.icon"
                  variant="outlined"
                  density="comfortable"
                  :hint="field.hintKey ? $t(field.hintKey) : undefined"
                  :persistent-hint="!!field.hintKey"
                />
                <v-text-field
                  v-else
                  v-model.number="formData[field.key]"
                  :label="$t(field.labelKey)"
                  :prepend-icon="field.icon"
                  type="number"
                  :step="field.step"
                  :min="field.min"
                  :max="field.max"
                  variant="outlined"
                  density="comfortable"
                  :rules="field.rules.map(r => rules[r])"
                  :suffix="field.suffix"
                />
              </v-col>
            </v-row>
          </v-form>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="editDialog = false">{{ $t('common.cancel') }}</v-btn>
          <v-btn color="primary" :loading="saving" :disabled="!formValid" @click="saveConfig">
            {{ $t('common.save') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Confirm Reset Dialog -->
    <v-dialog v-model="confirmResetDialog" max-width="400">
      <v-card>
        <v-card-title class="text-warning">
          <v-icon class="mr-2" color="warning">mdi-alert</v-icon>
          {{ $t('admin.clientConfig.confirmReset') }}
        </v-card-title>
        <v-card-text>
          {{ $t('admin.clientConfig.confirmResetMessage', { client: selectedClientName }) }}
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="confirmResetDialog = false">{{ $t('common.cancel') }}</v-btn>
          <v-btn color="warning" :loading="resetting" @click="resetToDefaults">
            {{ $t('admin.clientConfig.reset') }}
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
import { useClientConfigData } from '@/composables/useClientConfigData'
import { useClientConfigForms } from '@/composables/useClientConfigForms'

// Simple ConfigValueCard component inline
const ConfigValueCard = {
  props: {
    label: String,
    value: [String, Number],
    isDefault: Boolean
  },
  template: `
    <div class="d-flex justify-space-between align-center pa-3 rounded" :class="isDefault ? 'bg-grey-lighten-4' : 'bg-success-lighten-5'">
      <span class="text-body-2">{{ label }}</span>
      <v-chip :size="'small'" :color="isDefault ? 'grey' : 'success'">{{ value }}</v-chip>
    </div>
  `
}

// Data fetching and display logic
const {
  loadingClients,
  loadingConfig,
  clients,
  selectedClientId,
  clientConfig,
  globalDefaults,
  snackbar,
  selectedClientName,
  configSections,
  formatLabel,
  formatValue,
  showSnackbar,
  loadClientConfig,
  initialize
} = useClientConfigData()

// Form and submission logic
const {
  editDialog,
  confirmResetDialog,
  formValid,
  configForm,
  saving,
  resetting,
  formData,
  otdModeOptions,
  rules,
  editFormFields,
  openEditDialog,
  confirmResetToDefaults,
  saveConfig,
  resetToDefaults
} = useClientConfigForms(
  () => selectedClientId.value,
  () => clientConfig.value,
  () => globalDefaults.value,
  showSnackbar,
  loadClientConfig
)

// Lifecycle
onMounted(async () => {
  await initialize()
})
</script>

<style scoped>
.bg-success-lighten-5 {
  background-color: rgba(76, 175, 80, 0.08);
}
</style>
