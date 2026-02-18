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
                {{ $t('admin.floatingPool.howToUse') }}
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

    <!-- How-to Guide Dialog (extracted sub-component) -->
    <FloatingPoolGuideDialog v-model="showGuide" />

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
import { onMounted } from 'vue'
import FloatingPoolGuideDialog from '@/components/admin/FloatingPoolGuideDialog.vue'
import useFloatingPoolData from '@/composables/useFloatingPoolData'
import useFloatingPoolForms from '@/composables/useFloatingPoolForms'

// Data composable: state, computed, fetch, helpers
const {
  loading,
  loadingInsights,
  statusFilter,
  clientFilter,
  snackbar,
  insightsPanel,
  insights,
  summary,
  utilizationPercent,
  statusOptions,
  clientOptions,
  availableEmployees,
  filteredEntries,
  tableHeaders,
  showSnackbar,
  getClientName,
  formatDate,
  fetchData,
  fetchInsights
} = useFloatingPoolData()

// Forms composable: dialogs, assign/unassign CRUD
const {
  assigning,
  unassigning,
  showGuide,
  assignDialog,
  openAssignDialog,
  openEditDialog,
  confirmAssignment,
  unassignEmployee
} = useFloatingPoolForms({ fetchData, showSnackbar })

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
