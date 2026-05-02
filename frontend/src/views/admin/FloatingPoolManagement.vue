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
            </div>
          </v-card-title>

          <v-card-text>
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
                        <div class="text-caption text-medium-emphasis mt-1">
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
                        :loading="loadingInsights"
                        @click="fetchInsights"
                      >
                        <v-icon left size="small">mdi-refresh</v-icon>
                        {{ $t('common.refresh') }}
                      </v-btn>
                    </div>
                  </template>
                </v-expansion-panel-text>
              </v-expansion-panel>
            </v-expansion-panels>

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
                <v-btn color="primary" :loading="loading" @click="fetchData">
                  <v-icon left>mdi-refresh</v-icon>
                  {{ $t('common.refresh') }}
                </v-btn>
              </v-col>
            </v-row>

            <AGGridBase
              :columnDefs="columnDefs"
              :rowData="filteredEntries"
              height="560px"
              :pagination="true"
              :paginationPageSize="25"
              :enableExcelPaste="false"
              entry-type="production"
              @cell-value-changed="onCellValueChanged"
            />
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <FloatingPoolGuideDialog v-model="showGuide" />
  </v-container>
</template>

<script setup>
/**
 * FloatingPoolManagement — Group H Surface #21 of the entry-interface audit.
 *
 * Migrated 2026-05-01 from a v-data-table list + 5-field assign /edit
 * dialog to an inline AG Grid surface. Each row is a pool entry; pool
 * membership is set elsewhere (employee admin), so this surface
 * intentionally has no Add Row.
 *
 * Inline-edit policy (see useFloatingPoolGridData.ts):
 *   - current_assignment (Client column): clear → POST /unassign;
 *     set → POST /assign with the row's current dates + notes.
 *   - available_from / available_to / notes on an assigned row: re-
 *     fires /assign (legacy "edit" dialog also re-POSTed /assign).
 *   - Same edits on an unassigned row: local-only.
 *
 * Action column: Unassign quick-action button when the row is
 * assigned. Filters, summary cards, simulation insights expansion
 * panel and How-to-Use guide dialog are preserved.
 */
import { onMounted } from 'vue'
import AGGridBase from '@/components/grids/AGGridBase.vue'
import FloatingPoolGuideDialog from '@/components/admin/FloatingPoolGuideDialog.vue'
import { useNotificationStore } from '@/stores/notificationStore'
import { ref } from 'vue'
import useFloatingPoolData from '@/composables/useFloatingPoolData'
import useFloatingPoolGridData from '@/composables/useFloatingPoolGridData'

const notificationStore = useNotificationStore()
const showGuide = ref(false)

const {
  loading,
  loadingInsights,
  entries,
  statusFilter,
  clientFilter,
  insightsPanel,
  insights,
  summary,
  utilizationPercent,
  statusOptions,
  clientOptions,
  filteredEntries,
  fetchData,
  fetchInsights,
} = useFloatingPoolData()

const { columnDefs, onCellValueChanged } = useFloatingPoolGridData({
  entries,
  clientOptions,
  fetchData,
  notify: notificationStore,
})

onMounted(() => {
  fetchData()
  fetchInsights()
})
</script>

<style scoped>
.gap-1 {
  gap: 4px;
}
.gap-2 {
  gap: 8px;
}
</style>
