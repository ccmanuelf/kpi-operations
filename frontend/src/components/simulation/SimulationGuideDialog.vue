<template>
  <v-dialog :model-value="modelValue" max-width="900" scrollable @update:model-value="$emit('update:modelValue', $event)">
    <v-card>
      <v-card-title class="bg-primary text-white">
        <v-icon start>mdi-help-circle</v-icon>
        {{ $t('simulation.guideTitle') }} - {{ t('simulation.guide.comprehensiveGuide') }}
      </v-card-title>
      <v-card-text class="pa-0" v-if="guide">
        <v-tabs v-model="localGuideTab" color="primary" grow>
          <v-tab value="quick-start">{{ t('simulation.guide.tabQuickStart') }}</v-tab>
          <v-tab value="examples">{{ t('simulation.guide.tabExamples') }}</v-tab>
          <v-tab value="workflows">{{ t('simulation.guide.tabWorkflows') }}</v-tab>
          <v-tab value="reference">{{ t('simulation.guide.tabReference') }}</v-tab>
        </v-tabs>

        <v-tabs-window v-model="localGuideTab" class="pa-4">
          <!-- Quick Start Tab -->
          <v-tabs-window-item value="quick-start">
            <v-alert type="info" variant="tonal" class="mb-4">
              <strong>{{ t('simulation.guide.welcomeTitle') }}</strong><br>
              {{ t('simulation.guide.welcomeDescription') }}
            </v-alert>

            <h3 class="mb-2">{{ t('simulation.guide.gettingStarted') }}</h3>
            <v-list density="compact">
              <v-list-item v-for="(step, idx) in guide.quick_start" :key="idx" :prepend-icon="'mdi-numeric-' + (idx + 1) + '-circle'">
                {{ step }}
              </v-list-item>
            </v-list>

            <v-divider class="my-4" />

            <h3 class="mb-2">{{ $t('simulation.bestPractices') }}</h3>
            <v-list density="compact">
              <v-list-item v-for="(practice, idx) in guide.best_practices" :key="idx" prepend-icon="mdi-check-circle" class="text-success">
                {{ practice }}
              </v-list-item>
            </v-list>
          </v-tabs-window-item>

          <!-- Examples Tab -->
          <v-tabs-window-item value="examples">
            <v-alert type="success" variant="tonal" class="mb-4">
              <strong>{{ t('simulation.guide.tryExamples') }}</strong><br>
              {{ t('simulation.guide.tryExamplesDescription') }}
            </v-alert>

            <v-row>
              <v-col cols="12" md="6" v-for="(scenario, idx) in guide.example_scenarios" :key="idx">
                <v-card variant="outlined" class="mb-3">
                  <v-card-title class="text-subtitle-1">
                    <v-icon start color="primary">mdi-play-circle</v-icon>
                    {{ scenario.name }}
                  </v-card-title>
                  <v-card-text>
                    <p class="mb-2">{{ scenario.description }}</p>
                    <v-chip size="small" color="info" class="mr-1" v-if="scenario.config_change">
                      {{ t('simulation.guide.configChange') }}
                    </v-chip>
                    <v-chip size="small" color="warning" v-if="scenario.station_modifications">
                      {{ t('simulation.guide.stationModification') }}
                    </v-chip>
                  </v-card-text>
                  <v-card-actions>
                    <v-btn size="small" color="primary" @click="$emit('load-example', scenario)">
                      {{ t('simulation.guide.tryThis') }}
                    </v-btn>
                  </v-card-actions>
                </v-card>
              </v-col>
            </v-row>

            <v-divider class="my-4" />

            <h3 class="mb-3">{{ t('simulation.guide.sampleDataForTesting') }}</h3>
            <v-card variant="outlined">
              <v-card-text>
                <v-row>
                  <v-col cols="6" md="3">
                    <div class="text-h5 text-primary">4</div>
                    <div class="text-caption">{{ t('simulation.guide.workStations') }}</div>
                  </v-col>
                  <v-col cols="6" md="3">
                    <div class="text-h5 text-primary">2</div>
                    <div class="text-caption">{{ t('simulation.guide.workersStation') }}</div>
                  </v-col>
                  <v-col cols="6" md="3">
                    <div class="text-h5 text-primary">15 min</div>
                    <div class="text-caption">{{ t('simulation.guide.cycleTime') }}</div>
                  </v-col>
                  <v-col cols="6" md="3">
                    <div class="text-h5 text-primary">8 hrs</div>
                    <div class="text-caption">{{ t('simulation.guide.shiftDuration') }}</div>
                  </v-col>
                </v-row>
                <v-btn color="primary" class="mt-3" @click="$emit('load-sample')">
                  {{ t('simulation.guide.loadSampleConfig') }}
                </v-btn>
              </v-card-text>
            </v-card>
          </v-tabs-window-item>

          <!-- Workflows Tab -->
          <v-tabs-window-item value="workflows">
            <v-alert type="warning" variant="tonal" class="mb-4">
              <strong>{{ t('simulation.guide.stepByStepWorkflows') }}</strong><br>
              {{ t('simulation.guide.stepByStepDescription') }}
            </v-alert>

            <v-expansion-panels>
              <v-expansion-panel :title="t('simulation.guide.workflow1Title')">
                <v-expansion-panel-text>
                  <v-stepper :items="['Define Target', 'Set Parameters', 'Calculate', 'Review']" alt-labels class="elevation-0">
                    <template v-slot:item.1>
                      <v-card flat>
                        <v-card-text>
                          <p><strong>Step 1:</strong> Go to the <strong>Capacity Planning</strong> tab</p>
                          <p>Enter your target production units (e.g., 500 units/day)</p>
                        </v-card-text>
                      </v-card>
                    </template>
                    <template v-slot:item.2>
                      <v-card flat>
                        <v-card-text>
                          <p><strong>Step 2:</strong> Set your shift hours (default: 8 hours)</p>
                          <p>Enter cycle time per unit (e.g., 0.25 hours = 15 minutes)</p>
                          <p>Adjust target efficiency (default: 85%)</p>
                        </v-card-text>
                      </v-card>
                    </template>
                    <template v-slot:item.3>
                      <v-card flat>
                        <v-card-text>
                          <p><strong>Step 3:</strong> Click <strong>Calculate</strong></p>
                          <p>The system will compute required employees including buffer</p>
                        </v-card-text>
                      </v-card>
                    </template>
                    <template v-slot:item.4>
                      <v-card flat>
                        <v-card-text>
                          <p><strong>Step 4:</strong> Review the results showing:</p>
                          <ul>
                            <li>Required employees</li>
                            <li>Buffer employees (for absenteeism)</li>
                            <li>Total recommended staffing</li>
                          </ul>
                        </v-card-text>
                      </v-card>
                    </template>
                  </v-stepper>
                </v-expansion-panel-text>
              </v-expansion-panel>

              <v-expansion-panel :title="t('simulation.guide.workflow2Title')">
                <v-expansion-panel-text>
                  <v-stepper :items="['Configure', 'Load', 'Run', 'Analyze']" alt-labels class="elevation-0">
                    <template v-slot:item.1>
                      <v-card flat>
                        <v-card-text>
                          <p><strong>Step 1:</strong> Go to <strong>Production Line Simulation</strong> tab</p>
                          <p>Configure number of stations, workers per station, and floating pool size</p>
                        </v-card-text>
                      </v-card>
                    </template>
                    <template v-slot:item.2>
                      <v-card flat>
                        <v-card-text>
                          <p><strong>Step 2:</strong> Click <strong>Load Configuration</strong></p>
                          <p>This generates a production line based on your settings</p>
                        </v-card-text>
                      </v-card>
                    </template>
                    <template v-slot:item.3>
                      <v-card flat>
                        <v-card-text>
                          <p><strong>Step 3:</strong> Set simulation duration (default: 8 hours)</p>
                          <p>Click <strong>Run Simulation</strong></p>
                        </v-card-text>
                      </v-card>
                    </template>
                    <template v-slot:item.4>
                      <v-card flat>
                        <v-card-text>
                          <p><strong>Step 4:</strong> Review simulation results:</p>
                          <ul>
                            <li>Units completed and throughput</li>
                            <li>Efficiency and quality yield</li>
                            <li>Station utilization (identify bottlenecks)</li>
                            <li>Recommendations for improvement</li>
                          </ul>
                        </v-card-text>
                      </v-card>
                    </template>
                  </v-stepper>
                </v-expansion-panel-text>
              </v-expansion-panel>

              <v-expansion-panel :title="t('simulation.guide.workflow3Title')">
                <v-expansion-panel-text>
                  <v-stepper :items="['Baseline', 'Create Scenarios', 'Compare', 'Decide']" alt-labels class="elevation-0">
                    <template v-slot:item.1>
                      <v-card flat>
                        <v-card-text>
                          <p><strong>Step 1:</strong> First, load a baseline configuration in Production Line tab</p>
                          <p>This becomes your reference point for comparison</p>
                        </v-card-text>
                      </v-card>
                    </template>
                    <template v-slot:item.2>
                      <v-card flat>
                        <v-card-text>
                          <p><strong>Step 2:</strong> Go to <strong>Scenario Comparison</strong> tab</p>
                          <p>Create multiple scenarios with different configurations:</p>
                          <ul>
                            <li>Scenario A: Add 1 worker per station</li>
                            <li>Scenario B: Add 2 floating pool workers</li>
                            <li>Scenario C: Reduce cycle time 20%</li>
                          </ul>
                        </v-card-text>
                      </v-card>
                    </template>
                    <template v-slot:item.3>
                      <v-card flat>
                        <v-card-text>
                          <p><strong>Step 3:</strong> Click <strong>Compare Scenarios</strong></p>
                          <p>System runs simulation for each scenario</p>
                        </v-card-text>
                      </v-card>
                    </template>
                    <template v-slot:item.4>
                      <v-card flat>
                        <v-card-text>
                          <p><strong>Step 4:</strong> Review comparison table showing:</p>
                          <ul>
                            <li>Throughput change vs baseline</li>
                            <li>Efficiency improvement</li>
                            <li>Quality impact</li>
                            <li>Best scenario recommendation</li>
                          </ul>
                        </v-card-text>
                      </v-card>
                    </template>
                  </v-stepper>
                </v-expansion-panel-text>
              </v-expansion-panel>
            </v-expansion-panels>
          </v-tabs-window-item>

          <!-- Reference Tab -->
          <v-tabs-window-item value="reference">
            <h3 class="mb-3">{{ $t('simulation.metricsExplained') }}</h3>
            <v-table density="compact">
              <thead>
                <tr>
                  <th>{{ t('simulation.guide.metric') }}</th>
                  <th>{{ t('simulation.guide.metricDescription') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(desc, metric) in guide.metrics_explained" :key="metric">
                  <td><strong>{{ metric }}</strong></td>
                  <td>{{ desc }}</td>
                </tr>
              </tbody>
            </v-table>

            <v-divider class="my-4" />

            <h3 class="mb-3">{{ t('simulation.guide.configOptions') }}</h3>
            <v-expansion-panels v-if="guide.configuration_options">
              <v-expansion-panel :title="t('simulation.guide.lineConfig')">
                <v-expansion-panel-text>
                  <v-list density="compact">
                    <v-list-item v-for="(desc, key) in guide.configuration_options.line_config" :key="key">
                      <v-list-item-title><code>{{ key }}</code></v-list-item-title>
                      <v-list-item-subtitle>{{ desc }}</v-list-item-subtitle>
                    </v-list-item>
                  </v-list>
                </v-expansion-panel-text>
              </v-expansion-panel>
              <v-expansion-panel :title="t('simulation.guide.stationConfig')">
                <v-expansion-panel-text>
                  <v-list density="compact">
                    <v-list-item v-for="(desc, key) in guide.configuration_options.station_config" :key="key">
                      <v-list-item-title><code>{{ key }}</code></v-list-item-title>
                      <v-list-item-subtitle>{{ Array.isArray(desc) ? desc.join(', ') : desc }}</v-list-item-subtitle>
                    </v-list-item>
                  </v-list>
                </v-expansion-panel-text>
              </v-expansion-panel>
            </v-expansion-panels>
          </v-tabs-window-item>
        </v-tabs-window>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn color="primary" @click="$emit('update:modelValue', false)">{{ $t('common.close') }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  guide: {
    type: Object,
    default: null
  },
  guideTab: {
    type: String,
    default: 'quick-start'
  }
})

defineEmits(['update:modelValue', 'load-example', 'load-sample'])

const localGuideTab = ref(props.guideTab)

watch(() => props.guideTab, (val) => {
  localGuideTab.value = val
})
</script>
