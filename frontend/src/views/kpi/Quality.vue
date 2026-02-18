<template>
  <v-container fluid class="pa-4">
    <v-btn icon="mdi-arrow-left" variant="text" @click="$router.back()" class="mb-4" />

    <v-row>
      <v-col cols="12" md="6">
        <h1 class="text-h3">{{ t('kpi.quality') }}</h1>
        <p class="text-subtitle-1 text-grey-darken-1">{{ t('kpi.qualityDescription') }}</p>
      </v-col>
      <v-col cols="12" md="6" class="text-right">
        <v-chip :color="fpyColor" size="large" class="mr-2 text-white" variant="flat">
          FPY: {{ formatValue(qualityData?.fpy) }}%
        </v-chip>
        <v-chip color="grey-darken-2">{{ t('kpi.targetPercent', { value: 99 }) }}</v-chip>
      </v-col>
    </v-row>

    <!-- Filters -->
    <v-row class="mt-2">
      <v-col cols="12" md="4">
        <v-select
          v-model="selectedClient"
          :items="clients"
          item-title="client_name"
          item-value="client_id"
          :label="t('filters.client')"
          clearable
          density="compact"
          variant="outlined"
          @update:model-value="onClientChange"
        />
      </v-col>
      <v-col cols="12" md="3">
        <v-text-field
          v-model="startDate"
          type="date"
          :label="t('filters.startDate')"
          density="compact"
          variant="outlined"
          @change="onDateChange"
        />
      </v-col>
      <v-col cols="12" md="3">
        <v-text-field
          v-model="endDate"
          type="date"
          :label="t('filters.endDate')"
          density="compact"
          variant="outlined"
          @change="onDateChange"
        />
      </v-col>
      <v-col cols="12" md="2">
        <v-btn color="primary" block @click="doRefresh" :loading="loading">
          <v-icon left>mdi-refresh</v-icon> {{ t('common.refresh') }}
        </v-btn>
      </v-col>
    </v-row>

    <!-- Key Quality Metrics - Yield Percentages -->
    <v-row class="mt-4">
      <v-col cols="12" md="4">
        <v-tooltip location="bottom" max-width="350">
          <template v-slot:activator="{ props }">
            <v-card variant="outlined" :color="fpyColor" v-bind="props" class="cursor-help">
              <v-card-text>
                <div class="text-caption">{{ t('kpi.fpy') }}</div>
                <div class="text-h3 font-weight-bold">{{ formatValue(qualityData?.fpy) }}%</div>
                <div class="text-caption text-grey-darken-1">{{ t('kpi.targetPercent', { value: 99 }) }} | {{ t('kpi.firstAttemptPassRate') }}</div>
              </v-card-text>
            </v-card>
          </template>
          <div>
            <div class="tooltip-title">{{ t('common.formula') }}:</div>
            <div class="tooltip-formula">{{ t('kpi.tooltips.fpyFormula') }}</div>
            <div class="tooltip-title">{{ t('common.meaning') }}:</div>
            <div class="tooltip-meaning">{{ t('kpi.tooltips.fpyMeaning') }}</div>
          </div>
        </v-tooltip>
      </v-col>
      <v-col cols="12" md="4">
        <v-tooltip location="bottom" max-width="350">
          <template v-slot:activator="{ props }">
            <v-card variant="outlined" :color="rtyColor" v-bind="props" class="cursor-help">
              <v-card-text>
                <div class="text-caption">{{ t('kpi.rty') }}</div>
                <div class="text-h3 font-weight-bold">{{ formatValue(qualityData?.rty) }}%</div>
                <div class="text-caption text-grey-darken-1">{{ t('kpi.targetPercent', { value: 95 }) }} | {{ t('kpi.allStagesCombined') }}</div>
              </v-card-text>
            </v-card>
          </template>
          <div>
            <div class="tooltip-title">{{ t('common.formula') }}:</div>
            <div class="tooltip-formula">{{ t('kpi.tooltips.rtyFormula') }}</div>
            <div class="tooltip-title">{{ t('common.meaning') }}:</div>
            <div class="tooltip-meaning">{{ t('kpi.tooltips.rtyMeaning') }}</div>
          </div>
        </v-tooltip>
      </v-col>
      <v-col cols="12" md="4">
        <v-tooltip location="bottom" max-width="350">
          <template v-slot:activator="{ props }">
            <v-card variant="outlined" :color="finalYieldColor" v-bind="props" class="cursor-help">
              <v-card-text>
                <div class="text-caption">{{ t('kpi.finalYield') }}</div>
                <div class="text-h3 font-weight-bold">{{ formatValue(qualityData?.final_yield) }}%</div>
                <div class="text-caption text-grey-darken-1">{{ t('kpi.targetPercent', { value: 99 }) }} | {{ t('kpi.afterRework') }}</div>
              </v-card-text>
            </v-card>
          </template>
          <div>
            <div class="tooltip-title">{{ t('common.formula') }}:</div>
            <div class="tooltip-formula">{{ t('kpi.tooltips.finalYieldFormula') }}</div>
            <div class="tooltip-title">{{ t('common.meaning') }}:</div>
            <div class="tooltip-meaning">{{ t('kpi.tooltips.finalYieldMeaning') }}</div>
          </div>
        </v-tooltip>
      </v-col>
    </v-row>

    <!-- Key Quality Metrics - Counts -->
    <v-row class="mt-2">
      <v-col cols="12" md="4">
        <v-tooltip location="bottom" max-width="300">
          <template v-slot:activator="{ props }">
            <v-card variant="outlined" v-bind="props" class="cursor-help">
              <v-card-text>
                <div class="text-caption text-grey-darken-1">{{ t('kpi.totalUnitsInspected') }}</div>
                <div class="text-h4 font-weight-bold">{{ qualityData?.total_units || 0 }}</div>
              </v-card-text>
            </v-card>
          </template>
          <div>
            <div class="tooltip-title">{{ t('common.meaning') }}:</div>
            <div class="tooltip-meaning">{{ t('kpi.tooltips.totalInspectedMeaning') }}</div>
          </div>
        </v-tooltip>
      </v-col>
      <v-col cols="12" md="4">
        <v-tooltip location="bottom" max-width="300">
          <template v-slot:activator="{ props }">
            <v-card variant="outlined" v-bind="props" class="cursor-help">
              <v-card-text>
                <div class="text-caption text-grey-darken-1">{{ t('kpi.firstPassGood') }}</div>
                <div class="text-h4 font-weight-bold text-success">{{ qualityData?.first_pass_good || 0 }}</div>
              </v-card-text>
            </v-card>
          </template>
          <div>
            <div class="tooltip-title">{{ t('common.meaning') }}:</div>
            <div class="tooltip-meaning">{{ t('kpi.tooltips.firstPassGoodMeaning') }}</div>
          </div>
        </v-tooltip>
      </v-col>
      <v-col cols="12" md="4">
        <v-tooltip location="bottom" max-width="300">
          <template v-slot:activator="{ props }">
            <v-card variant="outlined" v-bind="props" class="cursor-help">
              <v-card-text>
                <div class="text-caption text-grey-darken-1">{{ t('kpi.totalScrapped') }}</div>
                <div class="text-h4 font-weight-bold text-error">{{ qualityData?.total_scrapped || 0 }}</div>
              </v-card-text>
            </v-card>
          </template>
          <div>
            <div class="tooltip-title">{{ t('common.meaning') }}:</div>
            <div class="tooltip-meaning">{{ t('kpi.tooltips.totalScrappedMeaning') }}</div>
          </div>
        </v-tooltip>
      </v-col>
    </v-row>

    <!-- Repair vs Rework Breakdown - Phase 6.5 -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card>
          <v-card-title class="d-flex align-center">
            <v-icon class="mr-2">mdi-tools</v-icon>
            {{ t('kpi.repairReworkBreakdown') }}
            <v-chip v-if="repairBreakdown?.rty_breakdown?.interpretation" class="ml-3" :color="getInterpretationColor(repairBreakdown?.rty_breakdown?.interpretation)" size="small" variant="tonal">
              {{ repairBreakdown?.rty_breakdown?.interpretation }}
            </v-chip>
          </v-card-title>
          <v-card-text>
            <v-row>
              <!-- Rework Rate -->
              <v-col cols="6" md="3">
                <v-tooltip location="bottom" max-width="350">
                  <template v-slot:activator="{ props }">
                    <v-card variant="outlined" color="info" v-bind="props" class="cursor-help">
                      <v-card-text class="text-center">
                        <v-icon color="info" size="24" class="mb-1">mdi-wrench</v-icon>
                        <div class="text-caption">{{ t('kpi.reworkRate') }}</div>
                        <div class="text-h5 font-weight-bold">{{ formatValue(repairBreakdown?.fpy_breakdown?.rework_rate) }}%</div>
                        <div class="text-caption">{{ repairBreakdown?.fpy_breakdown?.units_reworked || 0 }} {{ t('common.units') }}</div>
                      </v-card-text>
                    </v-card>
                  </template>
                  <div>
                    <div class="tooltip-title">{{ t('kpi.reworkRateTooltipTitle') }}</div>
                    <div class="tooltip-meaning">{{ t('kpi.reworkRateTooltipMeaning') }}</div>
                  </div>
                </v-tooltip>
              </v-col>

              <!-- Repair Rate -->
              <v-col cols="6" md="3">
                <v-tooltip location="bottom" max-width="350">
                  <template v-slot:activator="{ props }">
                    <v-card variant="outlined" color="warning" v-bind="props" class="cursor-help">
                      <v-card-text class="text-center">
                        <v-icon color="warning" size="24" class="mb-1">mdi-hammer-wrench</v-icon>
                        <div class="text-caption">{{ t('kpi.repairRate') }}</div>
                        <div class="text-h5 font-weight-bold">{{ formatValue(repairBreakdown?.fpy_breakdown?.repair_rate) }}%</div>
                        <div class="text-caption">{{ repairBreakdown?.fpy_breakdown?.units_requiring_repair || 0 }} {{ t('common.units') }}</div>
                      </v-card-text>
                    </v-card>
                  </template>
                  <div>
                    <div class="tooltip-title">{{ t('kpi.repairRateTooltipTitle') }}</div>
                    <div class="tooltip-meaning">{{ t('kpi.repairRateTooltipMeaning') }}</div>
                  </div>
                </v-tooltip>
              </v-col>

              <!-- Scrap Rate -->
              <v-col cols="6" md="3">
                <v-tooltip location="bottom" max-width="350">
                  <template v-slot:activator="{ props }">
                    <v-card variant="outlined" color="error" v-bind="props" class="cursor-help">
                      <v-card-text class="text-center">
                        <v-icon color="error" size="24" class="mb-1">mdi-delete</v-icon>
                        <div class="text-caption">{{ t('kpi.scrapRate') }}</div>
                        <div class="text-h5 font-weight-bold">{{ formatValue(repairBreakdown?.fpy_breakdown?.scrap_rate) }}%</div>
                        <div class="text-caption">{{ repairBreakdown?.fpy_breakdown?.units_scrapped || 0 }} {{ t('common.units') }}</div>
                      </v-card-text>
                    </v-card>
                  </template>
                  <div>
                    <div class="tooltip-title">{{ t('kpi.scrapRateTooltipTitle') }}</div>
                    <div class="tooltip-meaning">{{ t('kpi.scrapRateTooltipMeaning') }}</div>
                  </div>
                </v-tooltip>
              </v-col>

              <!-- Recovery Rate -->
              <v-col cols="6" md="3">
                <v-tooltip location="bottom" max-width="350">
                  <template v-slot:activator="{ props }">
                    <v-card variant="outlined" color="success" v-bind="props" class="cursor-help">
                      <v-card-text class="text-center">
                        <v-icon color="success" size="24" class="mb-1">mdi-recycle</v-icon>
                        <div class="text-caption">{{ t('kpi.recoveryRate') }}</div>
                        <div class="text-h5 font-weight-bold">{{ formatValue(repairBreakdown?.fpy_breakdown?.recovery_rate) }}%</div>
                        <div class="text-caption">{{ repairBreakdown?.fpy_breakdown?.recovered_units || 0 }} {{ t('common.recovered') }}</div>
                      </v-card-text>
                    </v-card>
                  </template>
                  <div>
                    <div class="tooltip-title">{{ t('kpi.recoveryRateTooltipTitle') }}</div>
                    <div class="tooltip-meaning">{{ t('kpi.recoveryRateTooltipMeaning') }}</div>
                  </div>
                </v-tooltip>
              </v-col>
            </v-row>

            <!-- Throughput Impact -->
            <v-row class="mt-3">
              <v-col cols="12">
                <v-alert type="info" variant="tonal" density="compact">
                  <div class="d-flex align-center">
                    <v-icon class="mr-2">mdi-chart-timeline-variant</v-icon>
                    <div>
                      <strong>{{ t('kpi.throughputLoss') }}:</strong>
                      {{ formatValue(repairBreakdown?.rty_breakdown?.throughput_loss_percentage) }}%
                      <span class="text-caption ml-2">
                        ({{ t('kpi.rework') }}: {{ formatValue(repairBreakdown?.rty_breakdown?.rework_impact_percentage) }}% +
                        {{ t('kpi.repair') }}: {{ formatValue(repairBreakdown?.rty_breakdown?.repair_impact_percentage) }}%)
                      </span>
                    </div>
                  </div>
                </v-alert>
              </v-col>
            </v-row>

            <!-- Stage Details Expansion Panel -->
            <v-expansion-panels v-if="repairBreakdown?.rty_breakdown?.step_details?.length" class="mt-3">
              <v-expansion-panel>
                <v-expansion-panel-title>
                  <v-icon class="mr-2">mdi-format-list-bulleted</v-icon>
                  {{ t('kpi.stageBreakdown') }} ({{ repairBreakdown?.rty_breakdown?.step_details?.length || 0 }} {{ t('common.stages') }})
                </v-expansion-panel-title>
                <v-expansion-panel-text>
                  <v-table density="compact">
                    <thead>
                      <tr>
                        <th>{{ t('common.stage') }}</th>
                        <th class="text-right">{{ t('kpi.fpy') }}</th>
                        <th class="text-right">{{ t('kpi.inspected') }}</th>
                        <th class="text-right">{{ t('kpi.rework') }}</th>
                        <th class="text-right">{{ t('kpi.repair') }}</th>
                        <th class="text-right">{{ t('kpi.scrap') }}</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="step in repairBreakdown?.rty_breakdown?.step_details" :key="step.step">
                        <td>
                          <v-chip :color="getStageColor(step.step)" size="small" variant="tonal">
                            {{ step.step }}
                          </v-chip>
                        </td>
                        <td class="text-right">
                          <v-chip :color="getFPYColor(step.fpy_percentage)" size="small">
                            {{ step.fpy_percentage?.toFixed(1) }}%
                          </v-chip>
                        </td>
                        <td class="text-right">{{ step.total_inspected }}</td>
                        <td class="text-right">
                          <span :class="step.units_reworked > 0 ? 'text-info' : ''">{{ step.units_reworked }}</span>
                        </td>
                        <td class="text-right">
                          <span :class="step.units_requiring_repair > 0 ? 'text-warning' : ''">{{ step.units_requiring_repair }}</span>
                        </td>
                        <td class="text-right">
                          <span :class="step.units_scrapped > 0 ? 'text-error' : ''">{{ step.units_scrapped }}</span>
                        </td>
                      </tr>
                    </tbody>
                  </v-table>
                </v-expansion-panel-text>
              </v-expansion-panel>
            </v-expansion-panels>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Job RTY Summary - Phase 6.6 -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card>
          <v-card-title class="d-flex align-center">
            <v-icon class="mr-2">mdi-format-list-numbered</v-icon>
            {{ t('kpi.jobRtySummary') }}
            <v-spacer />
            <v-btn
              color="primary"
              variant="outlined"
              size="small"
              @click="doLoadJobRty"
              :loading="loadingJobRty"
            >
              <v-icon left>mdi-refresh</v-icon>
              {{ t('common.refresh') }}
            </v-btn>
          </v-card-title>
          <v-card-text>
            <v-row v-if="jobRtySummary">
              <v-col cols="6" md="3">
                <v-card variant="outlined">
                  <v-card-text class="text-center">
                    <div class="text-caption text-grey-darken-1">{{ t('jobs.totalJobsCompleted') }}</div>
                    <div class="text-h4 font-weight-bold">{{ jobRtySummary.total_jobs_completed || 0 }}</div>
                  </v-card-text>
                </v-card>
              </v-col>
              <v-col cols="6" md="3">
                <v-card variant="outlined" :color="getYieldColor(jobRtySummary.average_job_yield)">
                  <v-card-text class="text-center">
                    <div class="text-caption">{{ t('jobs.avgJobYield') }}</div>
                    <div class="text-h4 font-weight-bold">{{ formatValue(jobRtySummary.average_job_yield) }}%</div>
                  </v-card-text>
                </v-card>
              </v-col>
              <v-col cols="6" md="3">
                <v-card variant="outlined" :color="getYieldColor(jobRtySummary.overall_yield)">
                  <v-card-text class="text-center">
                    <div class="text-caption">{{ t('jobs.overallYield') }}</div>
                    <div class="text-h4 font-weight-bold">{{ formatValue(jobRtySummary.overall_yield) }}%</div>
                  </v-card-text>
                </v-card>
              </v-col>
              <v-col cols="6" md="3">
                <v-card variant="outlined" color="error">
                  <v-card-text class="text-center">
                    <div class="text-caption">{{ t('jobs.jobsBelowTarget') }}</div>
                    <div class="text-h4 font-weight-bold">{{ jobRtySummary.jobs_below_target || 0 }}</div>
                    <div class="text-caption">({{ t('jobs.target') }}: {{ jobRtySummary.target_threshold }}%)</div>
                  </v-card-text>
                </v-card>
              </v-col>
            </v-row>

            <!-- Top Scrap Operations -->
            <v-expansion-panels v-if="jobRtySummary?.top_scrap_operations?.length" class="mt-3">
              <v-expansion-panel>
                <v-expansion-panel-title>
                  <v-icon class="mr-2" color="error">mdi-alert-circle</v-icon>
                  {{ t('jobs.topScrapOperations') }} ({{ jobRtySummary.top_scrap_operations.length }})
                </v-expansion-panel-title>
                <v-expansion-panel-text>
                  <v-table density="compact">
                    <thead>
                      <tr>
                        <th>{{ t('jobs.jobId') }}</th>
                        <th>{{ t('workOrders.workOrderId') }}</th>
                        <th class="text-right">{{ t('jobs.completed') }}</th>
                        <th class="text-right">{{ t('jobs.scrapped') }}</th>
                        <th class="text-right">{{ t('jobs.yield') }}</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="job in jobRtySummary.top_scrap_operations" :key="job.job_id">
                        <td class="font-weight-medium">{{ job.job_id }}</td>
                        <td>{{ job.work_order_id }}</td>
                        <td class="text-right">{{ job.completed }}</td>
                        <td class="text-right text-error font-weight-medium">{{ job.scrapped }}</td>
                        <td class="text-right">
                          <v-chip :color="getYieldColor(job.yield_percentage)" size="small">
                            {{ job.yield_percentage?.toFixed(1) }}%
                          </v-chip>
                        </td>
                      </tr>
                    </tbody>
                  </v-table>
                </v-expansion-panel-text>
              </v-expansion-panel>
            </v-expansion-panels>

            <v-alert v-if="!jobRtySummary && !loadingJobRty" type="info" variant="tonal" class="mt-2">
              {{ t('jobs.noJobRtyData') }}
            </v-alert>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Quality Trend Chart -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card>
          <v-card-title>{{ t('kpi.qualityTrends') }}</v-card-title>
          <v-card-text>
            <Line v-if="chartData.labels.length" :data="chartData" :options="chartOptions" />
            <v-alert v-else type="info" variant="tonal">{{ t('kpi.noTrendData') }}</v-alert>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Quality Records Table -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card>
          <v-card-title>
            {{ t('quality.inspectionRecords') }}
            <v-spacer />
            <v-text-field
              v-model="tableSearch"
              append-icon="mdi-magnify"
              :label="t('common.search')"
              single-line
              hide-details
              density="compact"
              style="max-width: 300px"
            />
          </v-card-title>
          <v-card-text>
            <v-data-table
              :headers="qualityHistoryHeaders"
              :items="qualityHistory"
              :search="tableSearch"
              :loading="loading"
              :items-per-page="10"
              class="elevation-0"
            >
              <template v-slot:item.shift_date="{ item }">
                {{ formatDate(item.shift_date) }}
              </template>
              <template v-slot:item.inspection_stage="{ item }">
                <v-chip
                  :color="item.inspection_stage === 'Final' ? 'success' : item.inspection_stage === 'In-Process' ? 'info' : 'warning'"
                  size="small"
                  variant="tonal"
                >
                  {{ item.inspection_stage || t('common.na') }}
                </v-chip>
              </template>
              <template v-slot:item.fpy_percentage="{ item }">
                <v-chip :color="getFPYColor(calculateFPY(item))" size="small">
                  {{ formatFPY(item) }}%
                </v-chip>
              </template>
            </v-data-table>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Defect Analysis -->
    <v-row class="mt-4">
      <v-col cols="12" md="6">
        <v-card>
          <v-card-title>{{ t('quality.topDefectTypes') }}</v-card-title>
          <v-card-text>
            <v-data-table
              :headers="defectHeaders"
              :items="qualityData?.defects_by_type || []"
              density="compact"
            >
              <template v-slot:item.count="{ item }">
                <v-chip color="error" size="small">{{ item.count }}</v-chip>
              </template>
              <template v-slot:item.percentage="{ item }">
                <v-progress-linear
                  :model-value="item.percentage"
                  color="error"
                  height="20"
                >
                  <strong>{{ item.percentage?.toFixed(1) || 0 }}%</strong>
                </v-progress-linear>
              </template>
            </v-data-table>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="6">
        <v-card>
          <v-card-title>{{ t('quality.byProduct') }}</v-card-title>
          <v-card-text>
            <v-data-table
              :headers="productHeaders"
              :items="qualityData?.by_product || []"
              density="compact"
            >
              <template v-slot:item.fpy="{ item }">
                <v-chip :color="getFPYColor(item.fpy)" size="small">
                  {{ item.fpy?.toFixed(1) || 0 }}%
                </v-chip>
              </template>
            </v-data-table>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-overlay v-model="loading" class="align-center justify-center" contained>
      <v-progress-circular indeterminate size="64" color="primary" />
    </v-overlay>
  </v-container>
</template>

<script setup>
import { onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { Line } from 'vue-chartjs'
import { useKPIStore } from '@/stores/kpi'
import { useQualityData } from '@/composables/useQualityData'
import { useQualityCharts } from '@/composables/useQualityCharts'
import { useQualityFilters } from '@/composables/useQualityFilters'

const { t } = useI18n()
const kpiStore = useKPIStore()

const {
  loading, loadingJobRty, qualityHistory, repairBreakdown, jobRtySummary,
  qualityData, fpyColor, rtyColor, finalYieldColor,
  defectHeaders, productHeaders, qualityHistoryHeaders,
  formatValue, formatDate, formatFPY,
  getFPYColor, getInterpretationColor, getStageColor, getYieldColor,
  calculateFPY, refreshData, loadJobRtySummary
} = useQualityData()

const { chartData, chartOptions } = useQualityCharts()

const {
  clients, selectedClient, startDate, endDate, tableSearch, loadClients
} = useQualityFilters()

const doRefresh = () => refreshData(selectedClient.value, startDate.value, endDate.value)
const doLoadJobRty = () => loadJobRtySummary(selectedClient.value, startDate.value, endDate.value)

const onClientChange = () => {
  kpiStore.setClient(selectedClient.value)
  doRefresh()
}

const onDateChange = () => {
  kpiStore.setDateRange(startDate.value, endDate.value)
  doRefresh()
}

onMounted(async () => {
  loading.value = true
  try {
    await loadClients()
    kpiStore.setDateRange(startDate.value, endDate.value)
    await doRefresh()
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.cursor-help {
  cursor: help;
}
</style>

<style>
/* Tooltip styling - unscoped to affect Vuetify tooltip portal */
.v-tooltip > .v-overlay__content {
  background-color: rgba(33, 33, 33, 0.95) !important;
  color: #ffffff !important;
  padding: 12px 16px !important;
  font-size: 14px !important;
  line-height: 1.5 !important;
}

.v-tooltip .tooltip-title {
  font-weight: 600;
  margin-bottom: 4px;
  color: #90caf9;
}

.v-tooltip .tooltip-formula {
  font-family: 'Courier New', monospace;
  background-color: rgba(255, 255, 255, 0.1);
  padding: 6px 10px;
  border-radius: 4px;
  margin-bottom: 8px;
  color: #ffffff;
}

.v-tooltip .tooltip-meaning {
  color: rgba(255, 255, 255, 0.9);
}
</style>
