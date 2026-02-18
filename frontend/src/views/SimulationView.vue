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

    <!-- How-To Guide Dialog - Enhanced with Tabs -->
    <v-dialog v-model="showGuide" max-width="900" scrollable>
      <v-card>
        <v-card-title class="bg-primary text-white">
          <v-icon start>mdi-help-circle</v-icon>
          {{ $t('simulation.guideTitle') }} - Comprehensive Guide
        </v-card-title>
        <v-card-text class="pa-0" v-if="guide">
          <v-tabs v-model="guideTab" color="primary" grow>
            <v-tab value="quick-start">Quick Start</v-tab>
            <v-tab value="examples">Examples</v-tab>
            <v-tab value="workflows">Workflows</v-tab>
            <v-tab value="reference">Reference</v-tab>
          </v-tabs>

          <v-tabs-window v-model="guideTab" class="pa-4">
            <!-- Quick Start Tab -->
            <v-tabs-window-item value="quick-start">
              <v-alert type="info" variant="tonal" class="mb-4">
                <strong>Welcome to Simulation & Capacity Planning!</strong><br>
                This tool helps you model production scenarios, calculate staffing requirements, and optimize your manufacturing operations.
              </v-alert>

              <h3 class="mb-2">Getting Started</h3>
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
                <strong>Try These Example Scenarios</strong><br>
                Use these pre-configured examples to understand how the simulation works.
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
                        Config Change
                      </v-chip>
                      <v-chip size="small" color="warning" v-if="scenario.station_modifications">
                        Station Modification
                      </v-chip>
                    </v-card-text>
                    <v-card-actions>
                      <v-btn size="small" color="primary" @click="loadExampleScenario(scenario)">
                        Try This
                      </v-btn>
                    </v-card-actions>
                  </v-card>
                </v-col>
              </v-row>

              <v-divider class="my-4" />

              <h3 class="mb-3">Sample Data for Testing</h3>
              <v-card variant="outlined">
                <v-card-text>
                  <v-row>
                    <v-col cols="6" md="3">
                      <div class="text-h5 text-primary">4</div>
                      <div class="text-caption">Work Stations</div>
                    </v-col>
                    <v-col cols="6" md="3">
                      <div class="text-h5 text-primary">2</div>
                      <div class="text-caption">Workers/Station</div>
                    </v-col>
                    <v-col cols="6" md="3">
                      <div class="text-h5 text-primary">15 min</div>
                      <div class="text-caption">Cycle Time</div>
                    </v-col>
                    <v-col cols="6" md="3">
                      <div class="text-h5 text-primary">8 hrs</div>
                      <div class="text-caption">Shift Duration</div>
                    </v-col>
                  </v-row>
                  <v-btn color="primary" class="mt-3" @click="loadSampleData">
                    Load Sample Configuration
                  </v-btn>
                </v-card-text>
              </v-card>
            </v-tabs-window-item>

            <!-- Workflows Tab -->
            <v-tabs-window-item value="workflows">
              <v-alert type="warning" variant="tonal" class="mb-4">
                <strong>Step-by-Step Workflows</strong><br>
                Follow these guided workflows to accomplish common simulation tasks.
              </v-alert>

              <v-expansion-panels>
                <v-expansion-panel title="Workflow 1: Calculate Staffing Requirements">
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

                <v-expansion-panel title="Workflow 2: Run Production Line Simulation">
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

                <v-expansion-panel title="Workflow 3: Compare What-If Scenarios">
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
                    <th>Metric</th>
                    <th>Description</th>
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

              <h3 class="mb-3">Configuration Options</h3>
              <v-expansion-panels v-if="guide.configuration_options">
                <v-expansion-panel title="Line Configuration">
                  <v-expansion-panel-text>
                    <v-list density="compact">
                      <v-list-item v-for="(desc, key) in guide.configuration_options.line_config" :key="key">
                        <v-list-item-title><code>{{ key }}</code></v-list-item-title>
                        <v-list-item-subtitle>{{ desc }}</v-list-item-subtitle>
                      </v-list-item>
                    </v-list>
                  </v-expansion-panel-text>
                </v-expansion-panel>
                <v-expansion-panel title="Station Configuration">
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
import { useNotificationStore } from '@/stores/notificationStore'

const notificationStore = useNotificationStore()

const { t } = useI18n()

const activeTab = ref('production-line')
const loading = ref(false)
const showGuide = ref(false)
const guideTab = ref('quick-start')
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
    notificationStore.showError('Failed to load simulation guide. Please refresh the page.')
  }
})

async function calculateCapacity() {
  loading.value = true
  try {
    const response = await calculateCapacityRequirements(capacityForm.value)
    capacityResult.value = response.data
  } catch (error) {
    console.error('Failed to calculate capacity:', error)
    notificationStore.showError('Failed to calculate capacity requirements. Please try again.')
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
    notificationStore.showError('Failed to load production line configuration. Please try again.')
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
    notificationStore.showError('Failed to run simulation. Please try again.')
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
    notificationStore.showError('Failed to compare scenarios. Please try again.')
  } finally {
    loading.value = false
  }
}

// Helper functions for guide examples
function loadExampleScenario(scenario) {
  // Apply example scenario configuration
  if (scenario.config_change) {
    // Parse config changes and apply to lineConfig
    if (scenario.name.toLowerCase().includes('floating')) {
      lineConfig.value.floating_pool_size = 2
    } else if (scenario.name.toLowerCase().includes('worker')) {
      lineConfig.value.workers_per_station = 3
    } else if (scenario.name.toLowerCase().includes('cycle') || scenario.name.toLowerCase().includes('time')) {
      lineConfig.value.base_cycle_time = 12 // 20% reduction from 15
    }
  }
  if (scenario.station_modifications) {
    lineConfig.value.num_stations = 5
  }

  // Close guide and switch to production line tab
  showGuide.value = false
  activeTab.value = 'production-line'

  // Automatically load the config
  loadDefaultConfig()
}

function loadSampleData() {
  // Load sample configuration for testing
  lineConfig.value = {
    num_stations: 4,
    workers_per_station: 2,
    floating_pool_size: 0,
    base_cycle_time: 15
  }
  simulationParams.value = {
    duration_hours: 8,
    random_seed: 42
  }

  // Close guide and switch to production line tab
  showGuide.value = false
  activeTab.value = 'production-line'

  // Automatically load the config
  loadDefaultConfig()
}
</script>
