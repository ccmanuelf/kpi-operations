<template>
  <div class="assumption-log-view">
    <!-- Header Info -->
    <v-card variant="outlined" class="mb-4">
      <v-card-text>
        <v-row align="center">
          <v-col cols="12" md="4">
            <div class="d-flex align-center">
              <v-avatar color="primary" size="48" class="mr-3">
                <v-icon color="white">mdi-engine</v-icon>
              </v-avatar>
              <div>
                <div class="text-caption text-medium-emphasis">Engine Version</div>
                <div class="text-h6 font-weight-bold">{{ assumptionLog.simulation_engine_version }}</div>
              </div>
            </div>
          </v-col>
          <v-col cols="12" md="4">
            <div class="d-flex align-center">
              <v-avatar color="info" size="48" class="mr-3">
                <v-icon color="white">mdi-cog</v-icon>
              </v-avatar>
              <div>
                <div class="text-caption text-medium-emphasis">Configuration Mode</div>
                <div class="text-h6 font-weight-bold text-capitalize">{{ assumptionLog.configuration_mode }}</div>
              </div>
            </div>
          </v-col>
          <v-col cols="12" md="4">
            <div class="d-flex align-center">
              <v-avatar color="success" size="48" class="mr-3">
                <v-icon color="white">mdi-clock</v-icon>
              </v-avatar>
              <div>
                <div class="text-caption text-medium-emphasis">Timestamp</div>
                <div class="text-subtitle-1 font-weight-bold">{{ formattedTimestamp }}</div>
              </div>
            </div>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <!-- Collapsible Sections -->
    <v-expansion-panels v-model="expandedPanels" multiple>
      <!-- Formulas Section -->
      <v-expansion-panel value="formulas">
        <v-expansion-panel-title>
          <v-icon class="mr-2">mdi-function</v-icon>
          <span class="font-weight-bold">Formulas & Calculations</span>
          <v-chip size="small" class="ml-2" color="primary" variant="tonal">
            {{ formulaCount }} formulas
          </v-chip>
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <v-table density="compact">
            <thead>
              <tr>
                <th class="text-left" style="width: 200px;">Formula Name</th>
                <th class="text-left">Implementation</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(formula, key) in assumptionLog.formula_implementations" :key="key">
                <td class="font-weight-medium">{{ formatFormulaKey(key) }}</td>
                <td>
                  <code class="formula-code">{{ formula }}</code>
                </td>
              </tr>
            </tbody>
          </v-table>

          <!-- Formula Details (expandable) -->
          <v-expansion-panels class="mt-3" variant="accordion">
            <v-expansion-panel v-for="(formula, key) in assumptionLog.formula_implementations" :key="key">
              <v-expansion-panel-title class="text-body-2">
                <v-icon size="small" class="mr-2">mdi-calculator</v-icon>
                {{ formatFormulaKey(key) }}
              </v-expansion-panel-title>
              <v-expansion-panel-text>
                <div class="pa-2 bg-grey-lighten-4 rounded">
                  <code class="text-body-2">{{ formula }}</code>
                </div>
                <div class="text-caption mt-2 text-medium-emphasis">
                  {{ getFormulaDescription(key) }}
                </div>
              </v-expansion-panel-text>
            </v-expansion-panel>
          </v-expansion-panels>
        </v-expansion-panel-text>
      </v-expansion-panel>

      <!-- Limitations Section -->
      <v-expansion-panel value="limitations">
        <v-expansion-panel-title>
          <v-icon class="mr-2" color="warning">mdi-alert-circle</v-icon>
          <span class="font-weight-bold">Limitations & Caveats</span>
          <v-chip size="small" class="ml-2" color="warning" variant="tonal">
            {{ assumptionLog.limitations_and_caveats?.length || 0 }} items
          </v-chip>
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <v-list density="compact" class="bg-transparent">
            <v-list-item
              v-for="(caveat, idx) in assumptionLog.limitations_and_caveats"
              :key="idx"
              class="limitation-item"
            >
              <template v-slot:prepend>
                <v-icon color="warning" size="small">mdi-information</v-icon>
              </template>
              <v-list-item-title class="text-body-2 text-wrap">
                {{ caveat }}
              </v-list-item-title>
            </v-list-item>
          </v-list>

          <v-alert v-if="!assumptionLog.limitations_and_caveats?.length" type="info" variant="tonal" density="compact">
            No limitations documented.
          </v-alert>
        </v-expansion-panel-text>
      </v-expansion-panel>

      <!-- Simulation Parameters Section -->
      <v-expansion-panel value="parameters">
        <v-expansion-panel-title>
          <v-icon class="mr-2">mdi-tune</v-icon>
          <span class="font-weight-bold">Simulation Parameters</span>
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <v-row>
            <v-col cols="12" md="6">
              <v-list density="compact" class="bg-transparent">
                <v-list-subheader>Default Values</v-list-subheader>
                <v-list-item>
                  <v-list-item-title>Default Operators</v-list-item-title>
                  <template v-slot:append>
                    <span class="font-weight-bold">1</span>
                  </template>
                </v-list-item>
                <v-list-item>
                  <v-list-item-title>Default Variability</v-list-item-title>
                  <template v-slot:append>
                    <span class="font-weight-bold">Triangular</span>
                  </template>
                </v-list-item>
                <v-list-item>
                  <v-list-item-title>Default Grade %</v-list-item-title>
                  <template v-slot:append>
                    <span class="font-weight-bold">85%</span>
                  </template>
                </v-list-item>
                <v-list-item>
                  <v-list-item-title>Default FPD %</v-list-item-title>
                  <template v-slot:append>
                    <span class="font-weight-bold">15%</span>
                  </template>
                </v-list-item>
              </v-list>
            </v-col>
            <v-col cols="12" md="6">
              <v-list density="compact" class="bg-transparent">
                <v-list-subheader>Configuration Limits</v-list-subheader>
                <v-list-item>
                  <v-list-item-title>Max Products</v-list-item-title>
                  <template v-slot:append>
                    <span class="font-weight-bold">5</span>
                  </template>
                </v-list-item>
                <v-list-item>
                  <v-list-item-title>Max Operations/Product</v-list-item-title>
                  <template v-slot:append>
                    <span class="font-weight-bold">50</span>
                  </template>
                </v-list-item>
                <v-list-item>
                  <v-list-item-title>Max Total Operations</v-list-item-title>
                  <template v-slot:append>
                    <span class="font-weight-bold">100</span>
                  </template>
                </v-list-item>
                <v-list-item>
                  <v-list-item-title>Max Horizon Days</v-list-item-title>
                  <template v-slot:append>
                    <span class="font-weight-bold">30</span>
                  </template>
                </v-list-item>
              </v-list>
            </v-col>
          </v-row>
        </v-expansion-panel-text>
      </v-expansion-panel>

      <!-- Technical Details Section -->
      <v-expansion-panel value="technical">
        <v-expansion-panel-title>
          <v-icon class="mr-2">mdi-code-braces</v-icon>
          <span class="font-weight-bold">Technical Details</span>
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <v-alert type="info" variant="tonal" density="compact" class="mb-3">
            This simulation uses SimPy discrete-event simulation engine for accurate modeling
            of production line dynamics including queuing, variability, and resource contention.
          </v-alert>

          <v-list density="compact" class="bg-transparent">
            <v-list-item>
              <template v-slot:prepend>
                <v-icon>mdi-server</v-icon>
              </template>
              <v-list-item-title>Simulation Framework</v-list-item-title>
              <v-list-item-subtitle>SimPy Discrete-Event Simulation</v-list-item-subtitle>
            </v-list-item>
            <v-list-item>
              <template v-slot:prepend>
                <v-icon>mdi-chart-bell-curve</v-icon>
              </template>
              <v-list-item-title>Variability Distribution</v-list-item-title>
              <v-list-item-subtitle>Triangular (min: SAM×0.85, mode: SAM, max: SAM×1.15)</v-list-item-subtitle>
            </v-list-item>
            <v-list-item>
              <template v-slot:prepend>
                <v-icon>mdi-package-variant</v-icon>
              </template>
              <v-list-item-title>Bundle Processing</v-list-item-title>
              <v-list-item-subtitle>Configurable bundle sizes with FIFO queue processing</v-list-item-subtitle>
            </v-list-item>
            <v-list-item>
              <template v-slot:prepend>
                <v-icon>mdi-gauge</v-icon>
              </template>
              <v-list-item-title>Bottleneck Detection</v-list-item-title>
              <v-list-item-subtitle>Stations with utilization ≥95% marked as bottlenecks</v-list-item-subtitle>
            </v-list-item>
          </v-list>
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>

    <!-- Export Raw Data -->
    <v-card variant="outlined" class="mt-4">
      <v-card-text class="d-flex align-center justify-space-between">
        <div>
          <div class="text-subtitle-1 font-weight-medium">Raw Assumption Log</div>
          <div class="text-caption text-medium-emphasis">Export complete simulation metadata as JSON</div>
        </div>
        <v-btn
          variant="outlined"
          color="primary"
          size="small"
          @click="copyToClipboard"
        >
          <v-icon start>mdi-content-copy</v-icon>
          Copy JSON
        </v-btn>
      </v-card-text>
    </v-card>

    <!-- Snackbar for copy confirmation -->
    <v-snackbar v-model="showCopied" color="success" :timeout="2000">
      Assumption log copied to clipboard
    </v-snackbar>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { format } from 'date-fns'

const props = defineProps({
  assumptionLog: {
    type: Object,
    required: true,
    default: () => ({
      simulation_engine_version: '',
      configuration_mode: '',
      timestamp: '',
      formula_implementations: {},
      limitations_and_caveats: []
    })
  }
})

// State
const expandedPanels = ref(['formulas', 'limitations'])
const showCopied = ref(false)

// Computed
const formattedTimestamp = computed(() => {
  try {
    return format(new Date(props.assumptionLog.timestamp), 'PPpp')
  } catch {
    return props.assumptionLog.timestamp
  }
})

const formulaCount = computed(() =>
  Object.keys(props.assumptionLog.formula_implementations || {}).length
)

// Methods
const formatFormulaKey = (key) => {
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase())
}

const getFormulaDescription = (key) => {
  const descriptions = {
    processing_time: 'Calculates actual processing time based on SAM, variability, and efficiency factors',
    utilization: 'Percentage of time a station is actively processing vs available time',
    throughput: 'Number of units completed per time period',
    cycle_time: 'Total time from bundle arrival to completion',
    wip: 'Work-in-progress pieces currently in the production system',
    coverage: 'Percentage of demand that can be met with current capacity',
    rebalancing: 'Algorithm for redistributing operators between stations'
  }

  // Find matching description
  for (const [pattern, desc] of Object.entries(descriptions)) {
    if (key.toLowerCase().includes(pattern)) {
      return desc
    }
  }
  return 'Formula used in simulation calculations'
}

const copyToClipboard = async () => {
  try {
    await navigator.clipboard.writeText(JSON.stringify(props.assumptionLog, null, 2))
    showCopied.value = true
  } catch (err) {
    console.error('Failed to copy:', err)
  }
}
</script>

<style scoped>
.assumption-log-view {
  padding: 0;
}

.formula-code {
  background: rgba(var(--v-theme-surface-variant), 0.5);
  padding: 4px 8px;
  border-radius: 4px;
  font-family: monospace;
  font-size: 0.85em;
  word-break: break-all;
}

.limitation-item {
  border-left: 3px solid rgba(var(--v-theme-warning), 0.5);
  margin-bottom: 4px;
  background: rgba(var(--v-theme-warning), 0.05);
}
</style>
