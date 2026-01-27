<template>
  <v-container fluid>
    <v-row>
      <v-col cols="12">
        <v-card>
          <v-card-title class="d-flex align-center">
            <v-icon start>mdi-chart-timeline-variant</v-icon>
            {{ $t('simulation.title') }}
            <v-spacer />
            <v-btn
              color="info"
              variant="outlined"
              size="small"
              @click="showGuide = true"
            >
              <v-icon start>mdi-help-circle</v-icon>
              {{ $t('simulation.howToUse') }}
            </v-btn>
          </v-card-title>
        </v-card>
      </v-col>
    </v-row>

    <!-- Tabs for different simulation types -->
    <v-row>
      <v-col cols="12">
        <v-tabs v-model="activeTab" color="primary">
          <v-tab value="capacity">{{ $t('simulation.capacityPlanning') }}</v-tab>
          <v-tab value="production-line">{{ $t('simulation.productionLine') }}</v-tab>
          <v-tab value="scenarios">{{ $t('simulation.scenarioComparison') }}</v-tab>
        </v-tabs>

        <v-tabs-window v-model="activeTab">
          <!-- Capacity Planning Tab -->
          <v-tabs-window-item value="capacity">
            <v-card flat>
              <v-card-text>
                <v-row>
                  <v-col cols="12" md="6">
                    <v-card variant="outlined">
                      <v-card-title>{{ $t('simulation.capacityRequirements') }}</v-card-title>
                      <v-card-text>
                        <v-form @submit.prevent="calculateCapacity">
                          <v-text-field
                            v-model.number="capacityForm.target_units"
                            :label="$t('simulation.targetUnits')"
                            type="number"
                            min="1"
                            required
                          />
                          <v-text-field
                            v-model.number="capacityForm.shift_hours"
                            :label="$t('simulation.shiftHours')"
                            type="number"
                            min="1"
                            max="24"
                          />
                          <v-text-field
                            v-model.number="capacityForm.cycle_time_hours"
                            :label="$t('simulation.cycleTimeHours')"
                            type="number"
                            step="0.01"
                            min="0.01"
                          />
                          <v-slider
                            v-model="capacityForm.target_efficiency"
                            :label="$t('simulation.targetEfficiency')"
                            min="50"
                            max="100"
                            thumb-label
                          />
                          <v-btn
                            type="submit"
                            color="primary"
                            :loading="loading"
                            block
                          >
                            {{ $t('simulation.calculate') }}
                          </v-btn>
                        </v-form>
                      </v-card-text>
                    </v-card>
                  </v-col>

                  <v-col cols="12" md="6">
                    <v-card variant="outlined" v-if="capacityResult">
                      <v-card-title>{{ $t('simulation.results') }}</v-card-title>
                      <v-card-text>
                        <v-list density="compact">
                          <v-list-item>
                            <template #prepend>
                              <v-icon color="primary">mdi-account-group</v-icon>
                            </template>
                            <v-list-item-title>{{ $t('simulation.requiredEmployees') }}</v-list-item-title>
                            <template #append>
                              <strong>{{ capacityResult.required_employees }}</strong>
                            </template>
                          </v-list-item>
                          <v-list-item>
                            <template #prepend>
                              <v-icon color="warning">mdi-account-plus</v-icon>
                            </template>
                            <v-list-item-title>{{ $t('simulation.bufferEmployees') }}</v-list-item-title>
                            <template #append>
                              <strong>{{ capacityResult.buffer_employees }}</strong>
                            </template>
                          </v-list-item>
                          <v-list-item>
                            <template #prepend>
                              <v-icon color="success">mdi-check-circle</v-icon>
                            </template>
                            <v-list-item-title>{{ $t('simulation.totalRecommended') }}</v-list-item-title>
                            <template #append>
                              <strong class="text-success">{{ capacityResult.total_recommended }}</strong>
                            </template>
                          </v-list-item>
                          <v-list-item>
                            <template #prepend>
                              <v-icon color="info">mdi-clock</v-icon>
                            </template>
                            <v-list-item-title>{{ $t('simulation.requiredHours') }}</v-list-item-title>
                            <template #append>
                              <strong>{{ capacityResult.required_hours?.toFixed(1) }}</strong>
                            </template>
                          </v-list-item>
                        </v-list>
                        <v-alert
                          v-for="(note, idx) in capacityResult.notes"
                          :key="idx"
                          type="info"
                          variant="tonal"
                          density="compact"
                          class="mt-2"
                        >
                          {{ note }}
                        </v-alert>
                      </v-card-text>
                    </v-card>
                  </v-col>
                </v-row>
              </v-card-text>
            </v-card>
          </v-tabs-window-item>

          <!-- Production Line Simulation Tab -->
          <v-tabs-window-item value="production-line">
            <v-card flat>
              <v-card-text>
                <v-row>
                  <!-- Configuration Panel -->
                  <v-col cols="12" md="4">
                    <v-card variant="outlined">
                      <v-card-title>{{ $t('simulation.lineConfiguration') }}</v-card-title>
                      <v-card-text>
                        <v-text-field
                          v-model.number="lineConfig.num_stations"
                          :label="$t('simulation.numStations')"
                          type="number"
                          min="2"
                          max="10"
                        />
                        <v-text-field
                          v-model.number="lineConfig.workers_per_station"
                          :label="$t('simulation.workersPerStation')"
                          type="number"
                          min="1"
                          max="10"
                        />
                        <v-text-field
                          v-model.number="lineConfig.floating_pool_size"
                          :label="$t('simulation.floatingPoolSize')"
                          type="number"
                          min="0"
                          max="10"
                        />
                        <v-text-field
                          v-model.number="lineConfig.base_cycle_time"
                          :label="$t('simulation.baseCycleTime')"
                          type="number"
                          min="1"
                          max="120"
                          suffix="min"
                        />
                        <v-text-field
                          v-model.number="simulationParams.duration_hours"
                          :label="$t('simulation.durationHours')"
                          type="number"
                          min="1"
                          max="24"
                        />
                        <v-btn
                          color="primary"
                          @click="loadDefaultConfig"
                          :loading="loading"
                          block
                          class="mb-2"
                        >
                          {{ $t('simulation.loadConfig') }}
                        </v-btn>
                        <v-btn
                          color="success"
                          @click="runSimulation"
                          :loading="loading"
                          :disabled="!productionLineConfig"
                          block
                        >
                          <v-icon start>mdi-play</v-icon>
                          {{ $t('simulation.runSimulation') }}
                        </v-btn>
                      </v-card-text>
                    </v-card>
                  </v-col>

                  <!-- Results Panel -->
                  <v-col cols="12" md="8">
                    <v-card variant="outlined" v-if="simulationResult">
                      <v-card-title>
                        {{ $t('simulation.simulationResults') }}
                        <v-chip class="ml-2" color="success" size="small">
                          {{ simulationResult.simulation_duration_hours }}h
                        </v-chip>
                      </v-card-title>
                      <v-card-text>
                        <!-- Summary Cards -->
                        <v-row>
                          <v-col cols="6" md="3">
                            <v-card variant="tonal" color="primary">
                              <v-card-text class="text-center">
                                <div class="text-h4">{{ simulationResult.summary?.units_completed }}</div>
                                <div class="text-caption">{{ $t('simulation.unitsCompleted') }}</div>
                              </v-card-text>
                            </v-card>
                          </v-col>
                          <v-col cols="6" md="3">
                            <v-card variant="tonal" color="success">
                              <v-card-text class="text-center">
                                <div class="text-h4">{{ simulationResult.summary?.throughput_per_hour }}</div>
                                <div class="text-caption">{{ $t('simulation.throughputPerHour') }}</div>
                              </v-card-text>
                            </v-card>
                          </v-col>
                          <v-col cols="6" md="3">
                            <v-card variant="tonal" color="info">
                              <v-card-text class="text-center">
                                <div class="text-h4">{{ simulationResult.summary?.efficiency?.toFixed(1) }}%</div>
                                <div class="text-caption">{{ $t('simulation.efficiency') }}</div>
                              </v-card-text>
                            </v-card>
                          </v-col>
                          <v-col cols="6" md="3">
                            <v-card variant="tonal" :color="simulationResult.summary?.quality_yield >= 95 ? 'success' : 'warning'">
                              <v-card-text class="text-center">
                                <div class="text-h4">{{ simulationResult.summary?.quality_yield?.toFixed(1) }}%</div>
                                <div class="text-caption">{{ $t('simulation.qualityYield') }}</div>
                              </v-card-text>
                            </v-card>
                          </v-col>
                        </v-row>

                        <!-- Bottleneck Info -->
                        <v-alert
                          v-if="simulationResult.bottleneck_analysis?.bottleneck_station"
                          type="warning"
                          variant="tonal"
                          class="mt-4"
                        >
                          <strong>{{ $t('simulation.bottleneck') }}:</strong>
                          {{ simulationResult.bottleneck_analysis.bottleneck_station }}
                          ({{ simulationResult.station_utilization?.[simulationResult.bottleneck_analysis.bottleneck_station] }}% {{ $t('simulation.utilization') }})
                        </v-alert>

                        <!-- Station Utilization -->
                        <v-card variant="outlined" class="mt-4" v-if="simulationResult.station_utilization">
                          <v-card-title class="text-subtitle-1">{{ $t('simulation.stationUtilization') }}</v-card-title>
                          <v-card-text>
                            <div v-for="(util, station) in simulationResult.station_utilization" :key="station" class="mb-2">
                              <div class="d-flex justify-space-between mb-1">
                                <span>{{ station }}</span>
                                <span>{{ util }}%</span>
                              </div>
                              <v-progress-linear
                                :model-value="util"
                                :color="util > 85 ? 'warning' : util > 70 ? 'primary' : 'success'"
                                height="12"
                                rounded
                              />
                            </div>
                          </v-card-text>
                        </v-card>

                        <!-- Recommendations -->
                        <v-card variant="outlined" class="mt-4" v-if="simulationResult.recommendations?.length">
                          <v-card-title class="text-subtitle-1">{{ $t('simulation.recommendations') }}</v-card-title>
                          <v-card-text>
                            <v-list density="compact">
                              <v-list-item
                                v-for="(rec, idx) in simulationResult.recommendations"
                                :key="idx"
                                prepend-icon="mdi-lightbulb"
                              >
                                {{ rec }}
                              </v-list-item>
                            </v-list>
                          </v-card-text>
                        </v-card>
                      </v-card-text>
                    </v-card>

                    <!-- Empty State -->
                    <v-card variant="outlined" v-else>
                      <v-card-text class="text-center py-8">
                        <v-icon size="64" color="grey">mdi-chart-timeline-variant</v-icon>
                        <div class="text-h6 mt-4">{{ $t('simulation.noResultsYet') }}</div>
                        <div class="text-body-2 text-grey">{{ $t('simulation.configureAndRun') }}</div>
                      </v-card-text>
                    </v-card>
                  </v-col>
                </v-row>
              </v-card-text>
            </v-card>
          </v-tabs-window-item>

          <!-- Scenario Comparison Tab -->
          <v-tabs-window-item value="scenarios">
            <v-card flat>
              <v-card-text>
                <v-row>
                  <v-col cols="12" md="4">
                    <v-card variant="outlined">
                      <v-card-title>{{ $t('simulation.defineScenarios') }}</v-card-title>
                      <v-card-text>
                        <v-text-field
                          v-model="newScenario.name"
                          :label="$t('simulation.scenarioName')"
                        />
                        <v-text-field
                          v-model.number="newScenario.workers_per_station"
                          :label="$t('simulation.workersPerStation')"
                          type="number"
                          min="1"
                          max="10"
                        />
                        <v-text-field
                          v-model.number="newScenario.floating_pool_size"
                          :label="$t('simulation.floatingPoolSize')"
                          type="number"
                          min="0"
                          max="10"
                        />
                        <v-btn
                          color="primary"
                          @click="addScenario"
                          :disabled="!newScenario.name"
                          block
                        >
                          <v-icon start>mdi-plus</v-icon>
                          {{ $t('simulation.addScenario') }}
                        </v-btn>

                        <v-divider class="my-4" />

                        <v-list density="compact" v-if="scenarios.length">
                          <v-list-subheader>{{ $t('simulation.scenariosToCompare') }}</v-list-subheader>
                          <v-list-item
                            v-for="(scenario, idx) in scenarios"
                            :key="idx"
                          >
                            <v-list-item-title>{{ scenario.name }}</v-list-item-title>
                            <v-list-item-subtitle>
                              {{ scenario.workers_per_station }} workers, {{ scenario.floating_pool_size }} pool
                            </v-list-item-subtitle>
                            <template #append>
                              <v-btn icon size="small" @click="removeScenario(idx)">
                                <v-icon>mdi-delete</v-icon>
                              </v-btn>
                            </template>
                          </v-list-item>
                        </v-list>

                        <v-btn
                          color="success"
                          @click="compareScenarios"
                          :loading="loading"
                          :disabled="scenarios.length < 1 || !productionLineConfig"
                          block
                          class="mt-4"
                        >
                          <v-icon start>mdi-compare</v-icon>
                          {{ $t('simulation.compareScenarios') }}
                        </v-btn>
                      </v-card-text>
                    </v-card>
                  </v-col>

                  <v-col cols="12" md="8">
                    <v-card variant="outlined" v-if="comparisonResult">
                      <v-card-title>{{ $t('simulation.comparisonResults') }}</v-card-title>
                      <v-card-text>
                        <v-table>
                          <thead>
                            <tr>
                              <th>{{ $t('simulation.scenario') }}</th>
                              <th class="text-right">{{ $t('simulation.throughput') }}</th>
                              <th class="text-right">{{ $t('simulation.efficiency') }}</th>
                              <th class="text-right">{{ $t('simulation.quality') }}</th>
                              <th class="text-right">{{ $t('simulation.change') }}</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr v-if="comparisonResult.baseline">
                              <td><strong>{{ comparisonResult.baseline.scenario }}</strong></td>
                              <td class="text-right">{{ comparisonResult.baseline.throughput_per_hour?.toFixed(1) }}</td>
                              <td class="text-right">{{ comparisonResult.baseline.efficiency?.toFixed(1) }}%</td>
                              <td class="text-right">{{ comparisonResult.baseline.quality_yield?.toFixed(1) }}%</td>
                              <td class="text-right">-</td>
                            </tr>
                            <tr v-for="scenario in comparisonResult.scenarios" :key="scenario.scenario">
                              <td>{{ scenario.scenario }}</td>
                              <td class="text-right">{{ scenario.throughput_per_hour?.toFixed(1) }}</td>
                              <td class="text-right">{{ scenario.efficiency?.toFixed(1) }}%</td>
                              <td class="text-right">{{ scenario.quality_yield?.toFixed(1) }}%</td>
                              <td class="text-right">
                                <v-chip
                                  :color="scenario.change_from_baseline?.throughput > 0 ? 'success' : 'error'"
                                  size="small"
                                >
                                  {{ scenario.change_from_baseline?.throughput > 0 ? '+' : '' }}{{ scenario.change_from_baseline?.throughput?.toFixed(1) }}%
                                </v-chip>
                              </td>
                            </tr>
                          </tbody>
                        </v-table>

                        <v-alert
                          v-if="comparisonResult.summary?.best_scenario"
                          type="success"
                          variant="tonal"
                          class="mt-4"
                        >
                          {{ $t('simulation.bestScenario') }}: <strong>{{ comparisonResult.summary.best_scenario }}</strong>
                          ({{ comparisonResult.summary.best_throughput?.toFixed(1) }} units/hour)
                        </v-alert>
                      </v-card-text>
                    </v-card>
                  </v-col>
                </v-row>
              </v-card-text>
            </v-card>
          </v-tabs-window-item>
        </v-tabs-window>
      </v-col>
    </v-row>

    <!-- How-To Guide Dialog -->
    <v-dialog v-model="showGuide" max-width="800">
      <v-card>
        <v-card-title>
          <v-icon start>mdi-help-circle</v-icon>
          {{ $t('simulation.guideTitle') }}
        </v-card-title>
        <v-card-text v-if="guide">
          <h3 class="mb-2">{{ $t('simulation.quickStart') }}</h3>
          <v-list density="compact">
            <v-list-item v-for="(step, idx) in guide.quick_start" :key="idx">
              {{ step }}
            </v-list-item>
          </v-list>

          <v-divider class="my-4" />

          <h3 class="mb-2">{{ $t('simulation.bestPractices') }}</h3>
          <v-list density="compact">
            <v-list-item v-for="(practice, idx) in guide.best_practices" :key="idx" prepend-icon="mdi-check">
              {{ practice }}
            </v-list-item>
          </v-list>

          <v-divider class="my-4" />

          <h3 class="mb-2">{{ $t('simulation.metricsExplained') }}</h3>
          <v-list density="compact">
            <v-list-item v-for="(desc, metric) in guide.metrics_explained" :key="metric">
              <v-list-item-title><strong>{{ metric }}</strong></v-list-item-title>
              <v-list-item-subtitle>{{ desc }}</v-list-item-subtitle>
            </v-list-item>
          </v-list>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn color="primary" @click="showGuide = false">{{ $t('common.close') }}</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  calculateCapacityRequirements,
  getProductionLineGuide,
  getDefaultProductionLineConfig,
  runProductionLineSimulation,
  compareProductionScenarios
} from '@/services/api/simulation'

const { t } = useI18n()

const activeTab = ref('production-line')
const loading = ref(false)
const showGuide = ref(false)
const guide = ref(null)

// Capacity Planning
const capacityForm = ref({
  target_units: 100,
  shift_hours: 8,
  cycle_time_hours: 0.25,
  target_efficiency: 85,
  absenteeism_rate: 5,
  include_buffer: true
})
const capacityResult = ref(null)

// Production Line Simulation
const lineConfig = ref({
  num_stations: 4,
  workers_per_station: 2,
  floating_pool_size: 0,
  base_cycle_time: 15
})
const simulationParams = ref({
  duration_hours: 8,
  random_seed: 42
})
const productionLineConfig = ref(null)
const simulationResult = ref(null)

// Scenario Comparison
const scenarios = ref([])
const newScenario = ref({
  name: '',
  workers_per_station: 2,
  floating_pool_size: 0
})
const comparisonResult = ref(null)

onMounted(async () => {
  try {
    const response = await getProductionLineGuide()
    guide.value = response.data
  } catch (error) {
    console.error('Failed to load guide:', error)
  }
})

async function calculateCapacity() {
  loading.value = true
  try {
    const response = await calculateCapacityRequirements(capacityForm.value)
    capacityResult.value = response.data
  } catch (error) {
    console.error('Failed to calculate capacity:', error)
  } finally {
    loading.value = false
  }
}

async function loadDefaultConfig() {
  loading.value = true
  try {
    const response = await getDefaultProductionLineConfig(lineConfig.value)
    productionLineConfig.value = response.data
  } catch (error) {
    console.error('Failed to load config:', error)
  } finally {
    loading.value = false
  }
}

async function runSimulation() {
  if (!productionLineConfig.value) return

  loading.value = true
  try {
    const response = await runProductionLineSimulation(productionLineConfig.value, simulationParams.value)
    simulationResult.value = response.data
  } catch (error) {
    console.error('Failed to run simulation:', error)
  } finally {
    loading.value = false
  }
}

function addScenario() {
  if (newScenario.value.name) {
    scenarios.value.push({ ...newScenario.value })
    newScenario.value = { name: '', workers_per_station: 2, floating_pool_size: 0 }
  }
}

function removeScenario(idx) {
  scenarios.value.splice(idx, 1)
}

async function compareScenarios() {
  if (!productionLineConfig.value || scenarios.value.length < 1) return

  loading.value = true
  try {
    const response = await compareProductionScenarios(
      productionLineConfig.value,
      scenarios.value,
      simulationParams.value
    )
    comparisonResult.value = response.data
  } catch (error) {
    console.error('Failed to compare scenarios:', error)
  } finally {
    loading.value = false
  }
}
</script>
