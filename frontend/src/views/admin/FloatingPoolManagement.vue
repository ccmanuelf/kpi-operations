<template>
  <v-container fluid>
    <v-row>
      <v-col cols="12">
        <v-card>
          <v-card-title class="d-flex justify-space-between align-center bg-primary">
            <div class="d-flex align-center">
              <v-icon class="mr-2">mdi-account-switch</v-icon>
              <span>{{ $t('admin.floatingPool.title') }}</span>
            </div>
            <div class="d-flex gap-2">
              <v-btn color="white" variant="text" @click="showGuide = true">
                <v-icon left>mdi-help-circle</v-icon>
                How to Use
              </v-btn>
              <v-btn color="white" variant="outlined" @click="openAssignDialog">
                <v-icon left>mdi-plus</v-icon>
                {{ $t('admin.floatingPool.assignEmployee') }}
              </v-btn>
            </div>
          </v-card-title>

          <v-card-text>
            <!-- Summary Cards -->
            <v-row class="mb-4">
              <v-col cols="12" md="3">
                <v-card variant="outlined" color="primary">
                  <v-card-text class="text-center">
                    <div class="text-h4">{{ summary.total }}</div>
                    <div class="text-caption">{{ $t('admin.floatingPool.totalEmployees') }}</div>
                  </v-card-text>
                </v-card>
              </v-col>
              <v-col cols="12" md="3">
                <v-card variant="outlined" color="success">
                  <v-card-text class="text-center">
                    <div class="text-h4">{{ summary.available }}</div>
                    <div class="text-caption">{{ $t('admin.floatingPool.available') }}</div>
                  </v-card-text>
                </v-card>
              </v-col>
              <v-col cols="12" md="3">
                <v-card variant="outlined" color="warning">
                  <v-card-text class="text-center">
                    <div class="text-h4">{{ summary.assigned }}</div>
                    <div class="text-caption">{{ $t('admin.floatingPool.currentlyAssigned') }}</div>
                  </v-card-text>
                </v-card>
              </v-col>
              <v-col cols="12" md="3">
                <v-card variant="outlined" color="info">
                  <v-card-text class="text-center">
                    <div class="text-h4">{{ utilizationPercent }}%</div>
                    <div class="text-caption">{{ $t('admin.floatingPool.utilization') }}</div>
                  </v-card-text>
                </v-card>
              </v-col>
            </v-row>

            <!-- Simulation Insights Panel -->
            <v-expansion-panels v-model="insightsPanel" class="mb-4">
              <v-expansion-panel value="insights">
                <v-expansion-panel-title>
                  <div class="d-flex align-center">
                    <v-icon class="mr-2" color="info">mdi-chart-timeline-variant</v-icon>
                    <span>{{ $t('admin.floatingPool.simulationInsights') }}</span>
                    <v-chip v-if="insights.recommendations?.length" size="small" color="warning" class="ml-2">
                      {{ insights.recommendations.length }} {{ $t('admin.floatingPool.recommendations') }}
                    </v-chip>
                  </div>
                </v-expansion-panel-title>
                <v-expansion-panel-text>
                  <v-row v-if="loadingInsights" class="py-4">
                    <v-col cols="12" class="text-center">
                      <v-progress-circular indeterminate color="primary" />
                      <div class="mt-2 text-grey">{{ $t('common.loading') }}</div>
                    </v-col>
                  </v-row>

                  <template v-else>
                    <!-- Staffing Scenarios -->
                    <div v-if="insights.staffing_scenarios?.length" class="mb-4">
                      <div class="text-subtitle-2 mb-2">
                        <v-icon size="small" class="mr-1">mdi-account-group</v-icon>
                        {{ $t('admin.floatingPool.staffingScenarios') }}
                      </div>
                      <v-table density="compact">
                        <thead>
                          <tr>
                            <th>{{ $t('simulation.staffing.scenario') }}</th>
                            <th>{{ $t('simulation.staffing.employees') }}</th>
                            <th>{{ $t('simulation.staffing.output') }}</th>
                            <th>{{ $t('simulation.staffing.efficiency') }}</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr v-for="scenario in insights.staffing_scenarios" :key="scenario.scenario">
                            <td>{{ scenario.scenario }}</td>
                            <td>{{ scenario.employees }}</td>
                            <td>{{ Math.round(scenario.units_per_shift || 0) }} {{ $t('common.units') }}</td>
                            <td>
                              <v-chip
                                :color="scenario.efficiency >= 85 ? 'success' : scenario.efficiency >= 70 ? 'warning' : 'error'"
                                size="small"
                              >
                                {{ scenario.efficiency?.toFixed(1) || 0 }}%
                              </v-chip>
                            </td>
                          </tr>
                        </tbody>
                      </v-table>
                    </div>

                    <!-- Recommendations -->
                    <div v-if="insights.recommendations?.length">
                      <div class="text-subtitle-2 mb-2">
                        <v-icon size="small" class="mr-1">mdi-lightbulb-outline</v-icon>
                        {{ $t('admin.floatingPool.recommendations') }}
                      </div>
                      <v-alert
                        v-for="(rec, idx) in insights.recommendations"
                        :key="idx"
                        :type="rec.priority === 'high' ? 'warning' : rec.priority === 'medium' ? 'info' : 'success'"
                        variant="tonal"
                        density="compact"
                        class="mb-2"
                      >
                        <div class="font-weight-medium">{{ rec.message }}</div>
                        <div class="text-caption text-grey-darken-1 mt-1">
                          <v-icon size="x-small" class="mr-1">mdi-arrow-right</v-icon>
                          {{ rec.action }}
                        </div>
                      </v-alert>
                    </div>

                    <div v-if="!insights.recommendations?.length && !insights.staffing_scenarios?.length" class="text-center py-4 text-grey">
                      <v-icon size="large" class="mb-2">mdi-information-outline</v-icon>
                      <div>{{ $t('admin.floatingPool.noInsightsAvailable') }}</div>
                    </div>

                    <div class="d-flex justify-end mt-3">
                      <v-btn
                        size="small"
                        variant="tonal"
                        color="primary"
                        @click="fetchInsights"
                        :loading="loadingInsights"
                      >
                        <v-icon left size="small">mdi-refresh</v-icon>
                        {{ $t('common.refresh') }}
                      </v-btn>
                    </div>
                  </template>
                </v-expansion-panel-text>
              </v-expansion-panel>
            </v-expansion-panels>

            <!-- Filter Controls -->
            <v-row class="mb-3">
              <v-col cols="12" md="4">
                <v-select
                  v-model="statusFilter"
                  :items="statusOptions"
                  :label="$t('admin.floatingPool.filterByStatus')"
                  variant="outlined"
                  density="compact"
                  clearable
                  hide-details
                />
              </v-col>
              <v-col cols="12" md="4">
                <v-select
                  v-model="clientFilter"
                  :items="clientOptions"
                  :label="$t('admin.floatingPool.filterByClient')"
                  variant="outlined"
                  density="compact"
                  clearable
                  hide-details
                  item-title="name"
                  item-value="client_id"
                />
              </v-col>
              <v-col cols="12" md="4">
                <v-btn color="primary" @click="fetchData" :loading="loading">
                  <v-icon left>mdi-refresh</v-icon>
                  {{ $t('common.refresh') }}
                </v-btn>
              </v-col>
            </v-row>

            <!-- Floating Pool Table -->
            <v-data-table
              :headers="tableHeaders"
              :items="filteredEntries"
              :loading="loading"
              :items-per-page="10"
              class="elevation-1"
            >
              <template v-slot:item.status="{ item }">
                <v-chip
                  :color="item.current_assignment ? 'warning' : 'success'"
                  size="small"
                  variant="flat"
                >
                  {{ item.current_assignment ? $t('admin.floatingPool.assigned') : $t('admin.floatingPool.available') }}
                </v-chip>
              </template>

              <template v-slot:item.current_assignment="{ item }">
                <span v-if="item.current_assignment">
                  {{ getClientName(item.current_assignment) }}
                </span>
                <span v-else class="text-grey">{{ $t('admin.floatingPool.notAssigned') }}</span>
              </template>

              <template v-slot:item.available_from="{ item }">
                {{ formatDate(item.available_from) }}
              </template>

              <template v-slot:item.available_to="{ item }">
                {{ formatDate(item.available_to) }}
              </template>

              <template v-slot:item.actions="{ item }">
                <div class="d-flex gap-1">
                  <v-btn
                    v-if="!item.current_assignment"
                    size="small"
                    color="primary"
                    variant="tonal"
                    @click="openAssignDialog(item)"
                  >
                    <v-icon size="small">mdi-account-arrow-right</v-icon>
                    {{ $t('admin.floatingPool.assign') }}
                  </v-btn>
                  <v-btn
                    v-else
                    size="small"
                    color="warning"
                    variant="tonal"
                    @click="unassignEmployee(item)"
                    :loading="unassigning === item.pool_id"
                  >
                    <v-icon size="small">mdi-account-remove</v-icon>
                    {{ $t('admin.floatingPool.unassign') }}
                  </v-btn>
                  <v-btn
                    size="small"
                    color="info"
                    variant="tonal"
                    @click="openEditDialog(item)"
                  >
                    <v-icon size="small">mdi-pencil</v-icon>
                  </v-btn>
                </div>
              </template>
            </v-data-table>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- How-to Guide Dialog -->
    <v-dialog v-model="showGuide" max-width="900" scrollable>
      <v-card>
        <v-card-title class="bg-primary text-white d-flex justify-space-between">
          <div class="d-flex align-center">
            <v-icon class="mr-2">mdi-help-circle</v-icon>
            Floating Pool Management Guide
          </div>
          <v-btn icon variant="text" color="white" @click="showGuide = false">
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </v-card-title>

        <v-card-text class="pa-0">
          <v-tabs v-model="guideTab" color="primary" grow>
            <v-tab value="overview">Overview</v-tab>
            <v-tab value="howto">How To Use</v-tab>
            <v-tab value="workflows">Workflows</v-tab>
            <v-tab value="insights">Simulation Insights</v-tab>
          </v-tabs>

          <v-tabs-window v-model="guideTab" class="pa-4">
            <!-- Overview Tab -->
            <v-tabs-window-item value="overview">
              <v-alert type="info" variant="tonal" class="mb-4">
                <strong>What is the Floating Pool?</strong><br>
                The Floating Pool is a shared workforce that can be temporarily assigned to different clients based on demand. This helps optimize staffing levels across your organization.
              </v-alert>

              <h4 class="mb-2">Key Concepts</h4>
              <v-list density="compact">
                <v-list-item prepend-icon="mdi-account-group">
                  <v-list-item-title><strong>Pool Employees</strong></v-list-item-title>
                  <v-list-item-subtitle>Workers designated as flexible resources who can work across multiple clients</v-list-item-subtitle>
                </v-list-item>
                <v-list-item prepend-icon="mdi-check-circle">
                  <v-list-item-title><strong>Available</strong></v-list-item-title>
                  <v-list-item-subtitle>Workers currently not assigned to any client, ready to be deployed</v-list-item-subtitle>
                </v-list-item>
                <v-list-item prepend-icon="mdi-briefcase">
                  <v-list-item-title><strong>Assigned</strong></v-list-item-title>
                  <v-list-item-subtitle>Workers currently working for a specific client</v-list-item-subtitle>
                </v-list-item>
                <v-list-item prepend-icon="mdi-percent">
                  <v-list-item-title><strong>Utilization</strong></v-list-item-title>
                  <v-list-item-subtitle>Percentage of pool employees currently assigned (higher = more efficient use)</v-list-item-subtitle>
                </v-list-item>
              </v-list>

              <v-divider class="my-4" />

              <h4 class="mb-2">Dashboard Cards Explained</h4>
              <v-row>
                <v-col cols="6" md="3">
                  <v-card variant="outlined" color="primary" class="text-center pa-2">
                    <v-icon>mdi-account-multiple</v-icon>
                    <div class="text-caption">Total Employees</div>
                    <div class="text-body-2">Total workers in the floating pool</div>
                  </v-card>
                </v-col>
                <v-col cols="6" md="3">
                  <v-card variant="outlined" color="success" class="text-center pa-2">
                    <v-icon>mdi-account-check</v-icon>
                    <div class="text-caption">Available</div>
                    <div class="text-body-2">Ready to be assigned</div>
                  </v-card>
                </v-col>
                <v-col cols="6" md="3">
                  <v-card variant="outlined" color="warning" class="text-center pa-2">
                    <v-icon>mdi-account-clock</v-icon>
                    <div class="text-caption">Assigned</div>
                    <div class="text-body-2">Currently working</div>
                  </v-card>
                </v-col>
                <v-col cols="6" md="3">
                  <v-card variant="outlined" color="info" class="text-center pa-2">
                    <v-icon>mdi-chart-donut</v-icon>
                    <div class="text-caption">Utilization</div>
                    <div class="text-body-2">Pool efficiency metric</div>
                  </v-card>
                </v-col>
              </v-row>
            </v-tabs-window-item>

            <!-- How To Use Tab -->
            <v-tabs-window-item value="howto">
              <h4 class="mb-3">Assigning an Employee</h4>
              <v-stepper :items="['Select', 'Configure', 'Confirm']" alt-labels class="elevation-0 mb-4">
                <template v-slot:item.1>
                  <v-card flat>
                    <v-card-text>
                      <ol>
                        <li>Find an available employee in the table (green "Available" badge)</li>
                        <li>Click the <v-btn size="x-small" color="primary" variant="tonal"><v-icon size="x-small">mdi-account-arrow-right</v-icon> Assign</v-btn> button</li>
                      </ol>
                    </v-card-text>
                  </v-card>
                </template>
                <template v-slot:item.2>
                  <v-card flat>
                    <v-card-text>
                      <ol>
                        <li>Select the target client from the dropdown</li>
                        <li>Optionally set availability dates (start and end)</li>
                        <li>Add notes if needed</li>
                      </ol>
                    </v-card-text>
                  </v-card>
                </template>
                <template v-slot:item.3>
                  <v-card flat>
                    <v-card-text>
                      <ol>
                        <li>Review the assignment details</li>
                        <li>Click "Confirm Assignment"</li>
                        <li>The employee status will change to "Assigned"</li>
                      </ol>
                    </v-card-text>
                  </v-card>
                </template>
              </v-stepper>

              <v-divider class="my-4" />

              <h4 class="mb-3">Unassigning an Employee</h4>
              <v-alert type="warning" variant="tonal" class="mb-3">
                Unassigning returns the employee to the available pool, making them ready for new assignments.
              </v-alert>
              <ol>
                <li>Find the assigned employee in the table</li>
                <li>Click the <v-btn size="x-small" color="warning" variant="tonal"><v-icon size="x-small">mdi-account-remove</v-icon> Unassign</v-btn> button</li>
                <li>The employee will immediately become available</li>
              </ol>

              <v-divider class="my-4" />

              <h4 class="mb-3">Using Filters</h4>
              <ul>
                <li><strong>Filter by Status:</strong> Show only "Available" or "Assigned" employees</li>
                <li><strong>Filter by Client:</strong> Show only employees assigned to a specific client</li>
              </ul>
            </v-tabs-window-item>

            <!-- Workflows Tab -->
            <v-tabs-window-item value="workflows">
              <h4 class="mb-3">Common Workflow Scenarios</h4>

              <v-expansion-panels>
                <v-expansion-panel title="Scenario 1: Rush Order Coverage">
                  <v-expansion-panel-text>
                    <v-alert type="info" variant="tonal" class="mb-3">
                      <strong>Situation:</strong> Client needs additional workers to meet a tight deadline
                    </v-alert>
                    <ol>
                      <li>Check the "Available" count in the summary cards</li>
                      <li>Filter by Status → "Available" to see all free workers</li>
                      <li>Assign multiple workers to the client needing help</li>
                      <li>Set the "Available To" date to when the rush period ends</li>
                      <li>Monitor the Simulation Insights for staffing recommendations</li>
                    </ol>
                  </v-expansion-panel-text>
                </v-expansion-panel>

                <v-expansion-panel title="Scenario 2: Covering Absenteeism">
                  <v-expansion-panel-text>
                    <v-alert type="warning" variant="tonal" class="mb-3">
                      <strong>Situation:</strong> A client has unexpected absences
                    </v-alert>
                    <ol>
                      <li>Check the absenteeism alert in the Alerts dashboard</li>
                      <li>Navigate to Floating Pool Management</li>
                      <li>Check available pool workers with relevant skills</li>
                      <li>Assign workers for the day or shift needed</li>
                      <li>Update attendance records accordingly</li>
                    </ol>
                  </v-expansion-panel-text>
                </v-expansion-panel>

                <v-expansion-panel title="Scenario 3: Balancing Workload">
                  <v-expansion-panel-text>
                    <v-alert type="success" variant="tonal" class="mb-3">
                      <strong>Situation:</strong> One client is over-staffed while another needs help
                    </v-alert>
                    <ol>
                      <li>Filter by Client → Select the over-staffed client</li>
                      <li>Identify workers who can be reassigned</li>
                      <li>Unassign them from the current client</li>
                      <li>Assign them to the client needing additional staff</li>
                      <li>Review the Simulation Insights for optimal distribution</li>
                    </ol>
                  </v-expansion-panel-text>
                </v-expansion-panel>
              </v-expansion-panels>

              <v-divider class="my-4" />

              <h4 class="mb-3">Best Practices</h4>
              <v-list density="compact">
                <v-list-item prepend-icon="mdi-check" class="text-success">
                  Keep at least 10-15% of pool workers available for emergencies
                </v-list-item>
                <v-list-item prepend-icon="mdi-check" class="text-success">
                  Set end dates for temporary assignments to auto-track availability
                </v-list-item>
                <v-list-item prepend-icon="mdi-check" class="text-success">
                  Review Simulation Insights regularly for optimization opportunities
                </v-list-item>
                <v-list-item prepend-icon="mdi-check" class="text-success">
                  Add notes to assignments for context and tracking
                </v-list-item>
                <v-list-item prepend-icon="mdi-close" class="text-error">
                  Avoid assigning all pool workers - maintain flexibility buffer
                </v-list-item>
              </v-list>
            </v-tabs-window-item>

            <!-- Simulation Insights Tab -->
            <v-tabs-window-item value="insights">
              <v-alert type="info" variant="tonal" class="mb-4">
                <strong>Simulation Insights</strong> uses production simulation data to provide staffing recommendations and scenario analysis.
              </v-alert>

              <h4 class="mb-3">Understanding Staffing Scenarios</h4>
              <p class="mb-3">The system simulates different staffing levels and shows predicted outcomes:</p>
              <v-table density="compact" class="mb-4">
                <thead>
                  <tr>
                    <th>Scenario</th>
                    <th>Meaning</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td><strong>Current</strong></td>
                    <td>Baseline with current assigned staff</td>
                  </tr>
                  <tr>
                    <td><strong>Minimum</strong></td>
                    <td>Fewest workers that meet basic production needs</td>
                  </tr>
                  <tr>
                    <td><strong>Optimal</strong></td>
                    <td>Best balance of efficiency and output</td>
                  </tr>
                  <tr>
                    <td><strong>Maximum</strong></td>
                    <td>Full utilization of available pool</td>
                  </tr>
                </tbody>
              </v-table>

              <h4 class="mb-3">Reading Recommendations</h4>
              <v-list density="compact">
                <v-list-item>
                  <template #prepend>
                    <v-chip size="small" color="warning">High Priority</v-chip>
                  </template>
                  <v-list-item-subtitle>Urgent actions that may impact production</v-list-item-subtitle>
                </v-list-item>
                <v-list-item>
                  <template #prepend>
                    <v-chip size="small" color="info">Medium Priority</v-chip>
                  </template>
                  <v-list-item-subtitle>Optimization suggestions for better efficiency</v-list-item-subtitle>
                </v-list-item>
                <v-list-item>
                  <template #prepend>
                    <v-chip size="small" color="success">Low Priority</v-chip>
                  </template>
                  <v-list-item-subtitle>Nice-to-have improvements</v-list-item-subtitle>
                </v-list-item>
              </v-list>

              <v-divider class="my-4" />

              <v-alert type="success" variant="tonal">
                <strong>Tip:</strong> Click "Refresh" in the Simulation Insights panel to get updated recommendations based on current data.
              </v-alert>
            </v-tabs-window-item>
          </v-tabs-window>
        </v-card-text>

        <v-card-actions>
          <v-spacer />
          <v-btn color="primary" @click="showGuide = false">Close</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Assignment Dialog -->
    <v-dialog v-model="assignDialog.show" max-width="500">
      <v-card>
        <v-card-title class="bg-primary">
          <v-icon class="mr-2">mdi-account-arrow-right</v-icon>
          {{ $t('admin.floatingPool.assignEmployee') }}
        </v-card-title>
        <v-card-text class="pt-4">
          <v-alert
            v-if="assignDialog.error"
            type="error"
            variant="tonal"
            class="mb-4"
            closable
            @click:close="assignDialog.error = null"
          >
            {{ assignDialog.error }}
          </v-alert>

          <v-select
            v-model="assignDialog.employee_id"
            :items="availableEmployees"
            :label="$t('admin.floatingPool.selectEmployee')"
            item-title="employee_name"
            item-value="employee_id"
            variant="outlined"
            :disabled="!!assignDialog.pool_id"
            class="mb-3"
          />

          <v-select
            v-model="assignDialog.client_id"
            :items="clientOptions"
            :label="$t('admin.floatingPool.selectClient')"
            item-title="name"
            item-value="client_id"
            variant="outlined"
            class="mb-3"
            :rules="[v => !!v || $t('common.required')]"
          />

          <v-row>
            <v-col cols="6">
              <v-text-field
                v-model="assignDialog.available_from"
                :label="$t('admin.floatingPool.availableFrom')"
                type="datetime-local"
                variant="outlined"
              />
            </v-col>
            <v-col cols="6">
              <v-text-field
                v-model="assignDialog.available_to"
                :label="$t('admin.floatingPool.availableTo')"
                type="datetime-local"
                variant="outlined"
              />
            </v-col>
          </v-row>

          <v-textarea
            v-model="assignDialog.notes"
            :label="$t('common.notes')"
            variant="outlined"
            rows="2"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="assignDialog.show = false">
            {{ $t('common.cancel') }}
          </v-btn>
          <v-btn
            color="primary"
            variant="flat"
            @click="confirmAssignment"
            :loading="assigning"
            :disabled="!assignDialog.client_id"
          >
            {{ $t('admin.floatingPool.confirmAssignment') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Snackbar for notifications -->
    <v-snackbar v-model="snackbar.show" :color="snackbar.color" :timeout="3000">
      {{ snackbar.message }}
    </v-snackbar>
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { format } from 'date-fns'
import api from '@/services/api'
import { getFloatingPoolSimulationInsights } from '@/services/api/simulation'

const { t } = useI18n()

// State
const loading = ref(false)
const loadingInsights = ref(false)
const showGuide = ref(false)
const guideTab = ref('overview')
const insightsPanel = ref(null)
const insights = ref({
  current_status: {},
  staffing_scenarios: [],
  recommendations: []
})
const assigning = ref(false)
const unassigning = ref(null)
const entries = ref([])
const clients = ref([])
const statusFilter = ref(null)
const clientFilter = ref(null)
const snackbar = ref({ show: false, message: '', color: 'success' })

// Assignment Dialog
const assignDialog = ref({
  show: false,
  pool_id: null,
  employee_id: null,
  client_id: null,
  available_from: null,
  available_to: null,
  notes: '',
  error: null
})

// Floating pool summary from API
const poolSummary = ref({
  total_floating_pool_employees: 0,
  currently_available: 0,
  currently_assigned: 0,
  available_employees: []
})

// Computed
const summary = computed(() => {
  // Use API summary if available, otherwise fall back to entries
  if (poolSummary.value.total_floating_pool_employees > 0) {
    return {
      total: poolSummary.value.total_floating_pool_employees,
      available: poolSummary.value.currently_available,
      assigned: poolSummary.value.currently_assigned
    }
  }
  const total = entries.value.length
  const assigned = entries.value.filter(e => e.current_assignment).length
  return {
    total,
    available: total - assigned,
    assigned
  }
})

const utilizationPercent = computed(() => {
  if (summary.value.total === 0) return 0
  return Math.round((summary.value.assigned / summary.value.total) * 100)
})

const statusOptions = computed(() => [
  { title: t('admin.floatingPool.available'), value: 'available' },
  { title: t('admin.floatingPool.assigned'), value: 'assigned' }
])

const clientOptions = computed(() => clients.value)

const availableEmployees = computed(() => {
  // Use pool summary's available employees if available
  if (poolSummary.value.available_employees?.length > 0) {
    return poolSummary.value.available_employees.map(e => ({
      employee_id: e.employee_id,
      employee_name: e.employee_name || `Employee #${e.employee_id}`
    }))
  }
  return entries.value.filter(e => !e.current_assignment).map(e => ({
    employee_id: e.employee_id,
    employee_name: e.employee_name || `Employee #${e.employee_id}`
  }))
})

const filteredEntries = computed(() => {
  let result = [...entries.value]

  if (statusFilter.value === 'available') {
    result = result.filter(e => !e.current_assignment)
  } else if (statusFilter.value === 'assigned') {
    result = result.filter(e => e.current_assignment)
  }

  if (clientFilter.value) {
    result = result.filter(e => e.current_assignment === clientFilter.value)
  }

  return result
})

const tableHeaders = computed(() => [
  { title: t('admin.floatingPool.employeeId'), key: 'employee_id', width: '100px' },
  { title: t('admin.floatingPool.employeeName'), key: 'employee_name' },
  { title: t('admin.floatingPool.status'), key: 'status', width: '120px' },
  { title: t('admin.floatingPool.assignedTo'), key: 'current_assignment' },
  { title: t('admin.floatingPool.availableFrom'), key: 'available_from', width: '150px' },
  { title: t('admin.floatingPool.availableTo'), key: 'available_to', width: '150px' },
  { title: t('common.actions'), key: 'actions', sortable: false, width: '200px' }
])

// Methods
const fetchData = async () => {
  loading.value = true
  try {
    const [poolResponse, summaryResponse, clientsResponse] = await Promise.all([
      api.get('/floating-pool'),
      api.get('/floating-pool/summary'),
      api.get('/clients')
    ])
    entries.value = poolResponse.data || []
    clients.value = clientsResponse.data || []

    // Update summary from API (includes employees with is_floating_pool=1)
    if (summaryResponse.data) {
      poolSummary.value = summaryResponse.data

      // If entries is empty but we have available employees, populate entries for display
      if (entries.value.length === 0 && summaryResponse.data.available_employees?.length > 0) {
        entries.value = summaryResponse.data.available_employees.map(emp => ({
          pool_id: null,
          employee_id: emp.employee_id,
          employee_code: emp.employee_code,
          employee_name: emp.employee_name,
          position: emp.position,
          current_assignment: null,
          available_from: null,
          available_to: null,
          notes: null
        }))
      }
    }
  } catch (error) {
    console.error('Error fetching floating pool data:', error)
    showSnackbar(t('common.error') + ': ' + (error.response?.data?.detail || error.message), 'error')
  } finally {
    loading.value = false
  }
}

const getClientName = (clientId) => {
  const client = clients.value.find(c => c.client_id === clientId)
  return client?.name || clientId
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  try {
    return format(new Date(dateStr), 'MMM dd, yyyy HH:mm')
  } catch {
    return dateStr
  }
}

const openAssignDialog = (item = null) => {
  assignDialog.value = {
    show: true,
    pool_id: item?.pool_id || null,
    employee_id: item?.employee_id || null,
    client_id: null,
    available_from: item?.available_from ? format(new Date(item.available_from), "yyyy-MM-dd'T'HH:mm") : null,
    available_to: item?.available_to ? format(new Date(item.available_to), "yyyy-MM-dd'T'HH:mm") : null,
    notes: item?.notes || '',
    error: null
  }
}

const openEditDialog = (item) => {
  openAssignDialog(item)
}

const confirmAssignment = async () => {
  if (!assignDialog.value.client_id) {
    assignDialog.value.error = t('admin.floatingPool.selectClientRequired')
    return
  }

  assigning.value = true
  assignDialog.value.error = null

  try {
    await api.post('/floating-pool/assign', {
      employee_id: assignDialog.value.employee_id,
      client_id: assignDialog.value.client_id,
      available_from: assignDialog.value.available_from || null,
      available_to: assignDialog.value.available_to || null,
      notes: assignDialog.value.notes || null
    })

    showSnackbar(t('admin.floatingPool.assignmentSuccess'), 'success')
    assignDialog.value.show = false
    await fetchData()
  } catch (error) {
    console.error('Error assigning employee:', error)
    const errorMessage = error.response?.data?.detail || error.message

    // Check for double assignment error
    if (errorMessage.includes('already assigned') || errorMessage.includes('double assignment')) {
      assignDialog.value.error = t('admin.floatingPool.doubleAssignmentError')
    } else {
      assignDialog.value.error = errorMessage
    }
  } finally {
    assigning.value = false
  }
}

const unassignEmployee = async (item) => {
  unassigning.value = item.pool_id
  try {
    await api.post('/floating-pool/unassign', {
      pool_id: item.pool_id
    })
    showSnackbar(t('admin.floatingPool.unassignmentSuccess'), 'success')
    await fetchData()
  } catch (error) {
    console.error('Error unassigning employee:', error)
    showSnackbar(t('common.error') + ': ' + (error.response?.data?.detail || error.message), 'error')
  } finally {
    unassigning.value = null
  }
}

const showSnackbar = (message, color = 'success') => {
  snackbar.value = { show: true, message, color }
}

// Fetch simulation insights
const fetchInsights = async () => {
  loadingInsights.value = true
  try {
    const response = await getFloatingPoolSimulationInsights({})
    insights.value = response.data || {
      current_status: {},
      staffing_scenarios: [],
      recommendations: []
    }
  } catch (error) {
    console.error('Error fetching simulation insights:', error)
    // Don't show error for insights - it's optional
  } finally {
    loadingInsights.value = false
  }
}

// Lifecycle
onMounted(() => {
  fetchData()
  fetchInsights()
})
</script>

<style scoped>
.gap-1 {
  gap: 4px;
}
</style>
