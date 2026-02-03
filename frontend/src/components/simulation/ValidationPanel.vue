<template>
  <v-card v-if="report" variant="outlined" :color="panelColor">
    <v-card-title class="d-flex align-center">
      <v-icon :color="iconColor" class="mr-2">{{ statusIcon }}</v-icon>
      <span>Validation {{ report.is_valid ? 'Passed' : 'Failed' }}</span>
      <v-spacer />
      <v-chip size="small" color="info" variant="tonal" class="mr-1">
        {{ report.products_count }} products
      </v-chip>
      <v-chip size="small" color="info" variant="tonal" class="mr-1">
        {{ report.operations_count }} operations
      </v-chip>
      <v-chip size="small" color="info" variant="tonal">
        {{ report.machine_tools_count }} machines
      </v-chip>
    </v-card-title>

    <v-card-text>
      <!-- Errors -->
      <div v-if="report.errors.length > 0" class="mb-4">
        <div class="text-subtitle-2 text-error mb-2">
          <v-icon size="small" color="error">mdi-alert-circle</v-icon>
          Errors ({{ report.errors.length }}) - Must fix before running
        </div>
        <v-list density="compact" class="bg-error-lighten-5 rounded">
          <v-list-item
            v-for="(error, idx) in report.errors"
            :key="'error-' + idx"
            :subtitle="error.recommendation"
          >
            <template v-slot:prepend>
              <v-icon color="error" size="small">mdi-close-circle</v-icon>
            </template>
            <v-list-item-title class="text-body-2">
              <span v-if="error.product" class="font-weight-medium">[{{ error.product }}]</span>
              {{ error.message }}
            </v-list-item-title>
          </v-list-item>
        </v-list>
      </div>

      <!-- Warnings -->
      <div v-if="report.warnings.length > 0" class="mb-4">
        <div class="text-subtitle-2 text-warning mb-2">
          <v-icon size="small" color="warning">mdi-alert</v-icon>
          Warnings ({{ report.warnings.length }}) - Review recommended
        </div>
        <v-expansion-panels variant="accordion">
          <v-expansion-panel>
            <v-expansion-panel-title>
              Show {{ report.warnings.length }} warning(s)
            </v-expansion-panel-title>
            <v-expansion-panel-text>
              <v-list density="compact">
                <v-list-item
                  v-for="(warning, idx) in report.warnings"
                  :key="'warning-' + idx"
                  :subtitle="warning.recommendation"
                >
                  <template v-slot:prepend>
                    <v-icon color="warning" size="small">mdi-alert</v-icon>
                  </template>
                  <v-list-item-title class="text-body-2">
                    <span v-if="warning.product" class="font-weight-medium">[{{ warning.product }}]</span>
                    {{ warning.message }}
                  </v-list-item-title>
                </v-list-item>
              </v-list>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
      </div>

      <!-- Info -->
      <div v-if="report.info.length > 0">
        <div class="text-subtitle-2 text-info mb-2">
          <v-icon size="small" color="info">mdi-information</v-icon>
          Information ({{ report.info.length }})
        </div>
        <v-expansion-panels variant="accordion">
          <v-expansion-panel>
            <v-expansion-panel-title>
              Show {{ report.info.length }} info message(s)
            </v-expansion-panel-title>
            <v-expansion-panel-text>
              <v-list density="compact">
                <v-list-item
                  v-for="(info, idx) in report.info"
                  :key="'info-' + idx"
                  :subtitle="info.recommendation"
                >
                  <template v-slot:prepend>
                    <v-icon color="info" size="small">mdi-information</v-icon>
                  </template>
                  <v-list-item-title class="text-body-2">
                    {{ info.message }}
                  </v-list-item-title>
                </v-list-item>
              </v-list>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
      </div>

      <!-- All Good -->
      <v-alert
        v-if="report.is_valid && report.warnings.length === 0"
        type="success"
        variant="tonal"
        density="compact"
      >
        Configuration is valid with no warnings. Ready to run simulation.
      </v-alert>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  report: {
    type: Object,
    default: null
  }
})

const panelColor = computed(() => {
  if (!props.report) return 'grey'
  if (props.report.errors.length > 0) return 'error'
  if (props.report.warnings.length > 0) return 'warning'
  return 'success'
})

const iconColor = computed(() => {
  if (!props.report) return 'grey'
  if (props.report.errors.length > 0) return 'error'
  if (props.report.warnings.length > 0) return 'warning'
  return 'success'
})

const statusIcon = computed(() => {
  if (!props.report) return 'mdi-help-circle'
  if (props.report.errors.length > 0) return 'mdi-close-circle'
  if (props.report.warnings.length > 0) return 'mdi-alert-circle'
  return 'mdi-check-circle'
})
</script>
