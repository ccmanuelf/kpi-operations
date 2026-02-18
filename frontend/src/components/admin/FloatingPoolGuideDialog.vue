<template>
  <v-dialog :model-value="modelValue" max-width="900" scrollable @update:model-value="$emit('update:modelValue', $event)">
    <v-card>
      <v-card-title class="bg-primary text-white d-flex justify-space-between">
        <div class="d-flex align-center">
          <v-icon class="mr-2">mdi-help-circle</v-icon>
          {{ $t('admin.floatingPool.guide') }}
        </div>
        <v-btn icon variant="text" color="white" @click="$emit('update:modelValue', false)">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>

      <v-card-text class="pa-0">
        <v-tabs v-model="guideTab" color="primary" grow>
          <v-tab value="overview">{{ $t('admin.floatingPool.guideOverview') }}</v-tab>
          <v-tab value="howto">{{ $t('admin.floatingPool.guideHowTo') }}</v-tab>
          <v-tab value="workflows">{{ $t('admin.floatingPool.guideWorkflows') }}</v-tab>
          <v-tab value="insights">{{ $t('admin.floatingPool.guideInsights') }}</v-tab>
        </v-tabs>

        <v-tabs-window v-model="guideTab" class="pa-4">
          <!-- Overview Tab -->
          <v-tabs-window-item value="overview">
            <v-alert type="info" variant="tonal" class="mb-4">
              <strong>{{ $t('admin.poolGuide.whatIsTitle') }}</strong><br>
              {{ $t('admin.poolGuide.whatIsDescription') }}
            </v-alert>

            <h4 class="mb-2">{{ $t('admin.poolGuide.keyConcepts') }}</h4>
            <v-list density="compact">
              <v-list-item prepend-icon="mdi-account-group">
                <v-list-item-title><strong>{{ $t('admin.poolGuide.poolEmployees') }}</strong></v-list-item-title>
                <v-list-item-subtitle>{{ $t('admin.poolGuide.poolEmployeesDesc') }}</v-list-item-subtitle>
              </v-list-item>
              <v-list-item prepend-icon="mdi-check-circle">
                <v-list-item-title><strong>{{ $t('admin.floatingPool.available') }}</strong></v-list-item-title>
                <v-list-item-subtitle>{{ $t('admin.poolGuide.availableDesc') }}</v-list-item-subtitle>
              </v-list-item>
              <v-list-item prepend-icon="mdi-briefcase">
                <v-list-item-title><strong>{{ $t('admin.floatingPool.assigned') }}</strong></v-list-item-title>
                <v-list-item-subtitle>{{ $t('admin.poolGuide.assignedDesc') }}</v-list-item-subtitle>
              </v-list-item>
              <v-list-item prepend-icon="mdi-percent">
                <v-list-item-title><strong>{{ $t('admin.floatingPool.utilization') }}</strong></v-list-item-title>
                <v-list-item-subtitle>{{ $t('admin.poolGuide.utilizationDesc') }}</v-list-item-subtitle>
              </v-list-item>
            </v-list>

            <v-divider class="my-4" />

            <h4 class="mb-2">{{ $t('admin.poolGuide.dashboardExplained') }}</h4>
            <v-row>
              <v-col cols="6" md="3">
                <v-card variant="outlined" color="primary" class="text-center pa-2">
                  <v-icon>mdi-account-multiple</v-icon>
                  <div class="text-caption">{{ $t('admin.floatingPool.totalEmployees') }}</div>
                  <div class="text-body-2">{{ $t('admin.poolGuide.totalDesc') }}</div>
                </v-card>
              </v-col>
              <v-col cols="6" md="3">
                <v-card variant="outlined" color="success" class="text-center pa-2">
                  <v-icon>mdi-account-check</v-icon>
                  <div class="text-caption">{{ $t('admin.floatingPool.available') }}</div>
                  <div class="text-body-2">{{ $t('admin.poolGuide.readyToAssign') }}</div>
                </v-card>
              </v-col>
              <v-col cols="6" md="3">
                <v-card variant="outlined" color="warning" class="text-center pa-2">
                  <v-icon>mdi-account-clock</v-icon>
                  <div class="text-caption">{{ $t('admin.floatingPool.assigned') }}</div>
                  <div class="text-body-2">{{ $t('admin.poolGuide.currentlyWorking') }}</div>
                </v-card>
              </v-col>
              <v-col cols="6" md="3">
                <v-card variant="outlined" color="info" class="text-center pa-2">
                  <v-icon>mdi-chart-donut</v-icon>
                  <div class="text-caption">{{ $t('admin.floatingPool.utilization') }}</div>
                  <div class="text-body-2">{{ $t('admin.poolGuide.efficiencyMetric') }}</div>
                </v-card>
              </v-col>
            </v-row>
          </v-tabs-window-item>

          <!-- How To Use Tab -->
          <v-tabs-window-item value="howto">
            <h4 class="mb-3">{{ $t('admin.poolGuide.assigningEmployee') }}</h4>
            <v-stepper :items="stepperAssign" alt-labels class="elevation-0 mb-4">
              <template v-slot:item.1>
                <v-card flat>
                  <v-card-text>
                    <ol>
                      <li>{{ $t('admin.poolGuide.assignStep1a') }}</li>
                      <li>{{ $t('admin.poolGuide.assignStep1b') }}</li>
                    </ol>
                  </v-card-text>
                </v-card>
              </template>
              <template v-slot:item.2>
                <v-card flat>
                  <v-card-text>
                    <ol>
                      <li>{{ $t('admin.poolGuide.assignStep2a') }}</li>
                      <li>{{ $t('admin.poolGuide.assignStep2b') }}</li>
                      <li>{{ $t('admin.poolGuide.assignStep2c') }}</li>
                    </ol>
                  </v-card-text>
                </v-card>
              </template>
              <template v-slot:item.3>
                <v-card flat>
                  <v-card-text>
                    <ol>
                      <li>{{ $t('admin.poolGuide.assignStep3a') }}</li>
                      <li>{{ $t('admin.poolGuide.assignStep3b') }}</li>
                      <li>{{ $t('admin.poolGuide.assignStep3c') }}</li>
                    </ol>
                  </v-card-text>
                </v-card>
              </template>
            </v-stepper>

            <v-divider class="my-4" />

            <h4 class="mb-3">{{ $t('admin.poolGuide.unassigningEmployee') }}</h4>
            <v-alert type="warning" variant="tonal" class="mb-3">
              {{ $t('admin.poolGuide.unassignWarning') }}
            </v-alert>
            <ol>
              <li>{{ $t('admin.poolGuide.unassignStep1') }}</li>
              <li>{{ $t('admin.poolGuide.unassignStep2') }}</li>
              <li>{{ $t('admin.poolGuide.unassignStep3') }}</li>
            </ol>

            <v-divider class="my-4" />

            <h4 class="mb-3">{{ $t('admin.poolGuide.usingFilters') }}</h4>
            <ul>
              <li><strong>{{ $t('admin.floatingPool.filterByStatus') }}:</strong> {{ $t('admin.poolGuide.filterStatusDesc') }}</li>
              <li><strong>{{ $t('admin.floatingPool.filterByClient') }}:</strong> {{ $t('admin.poolGuide.filterClientDesc') }}</li>
            </ul>
          </v-tabs-window-item>

          <!-- Workflows Tab -->
          <v-tabs-window-item value="workflows">
            <h4 class="mb-3">{{ $t('admin.poolGuide.commonWorkflows') }}</h4>

            <v-expansion-panels>
              <v-expansion-panel :title="$t('admin.poolGuide.scenarioRush')">
                <v-expansion-panel-text>
                  <v-alert type="info" variant="tonal" class="mb-3">
                    <strong>{{ $t('admin.poolGuide.situation') }}:</strong> {{ $t('admin.poolGuide.rushSituation') }}
                  </v-alert>
                  <ol>
                    <li>{{ $t('admin.poolGuide.rushStep1') }}</li>
                    <li>{{ $t('admin.poolGuide.rushStep2') }}</li>
                    <li>{{ $t('admin.poolGuide.rushStep3') }}</li>
                    <li>{{ $t('admin.poolGuide.rushStep4') }}</li>
                    <li>{{ $t('admin.poolGuide.rushStep5') }}</li>
                  </ol>
                </v-expansion-panel-text>
              </v-expansion-panel>

              <v-expansion-panel :title="$t('admin.poolGuide.scenarioAbsenteeism')">
                <v-expansion-panel-text>
                  <v-alert type="warning" variant="tonal" class="mb-3">
                    <strong>{{ $t('admin.poolGuide.situation') }}:</strong> {{ $t('admin.poolGuide.absentSituation') }}
                  </v-alert>
                  <ol>
                    <li>{{ $t('admin.poolGuide.absentStep1') }}</li>
                    <li>{{ $t('admin.poolGuide.absentStep2') }}</li>
                    <li>{{ $t('admin.poolGuide.absentStep3') }}</li>
                    <li>{{ $t('admin.poolGuide.absentStep4') }}</li>
                    <li>{{ $t('admin.poolGuide.absentStep5') }}</li>
                  </ol>
                </v-expansion-panel-text>
              </v-expansion-panel>

              <v-expansion-panel :title="$t('admin.poolGuide.scenarioBalance')">
                <v-expansion-panel-text>
                  <v-alert type="success" variant="tonal" class="mb-3">
                    <strong>{{ $t('admin.poolGuide.situation') }}:</strong> {{ $t('admin.poolGuide.balanceSituation') }}
                  </v-alert>
                  <ol>
                    <li>{{ $t('admin.poolGuide.balanceStep1') }}</li>
                    <li>{{ $t('admin.poolGuide.balanceStep2') }}</li>
                    <li>{{ $t('admin.poolGuide.balanceStep3') }}</li>
                    <li>{{ $t('admin.poolGuide.balanceStep4') }}</li>
                    <li>{{ $t('admin.poolGuide.balanceStep5') }}</li>
                  </ol>
                </v-expansion-panel-text>
              </v-expansion-panel>
            </v-expansion-panels>

            <v-divider class="my-4" />

            <h4 class="mb-3">{{ $t('admin.poolGuide.bestPractices') }}</h4>
            <v-list density="compact">
              <v-list-item prepend-icon="mdi-check" class="text-success">
                {{ $t('admin.poolGuide.bp1') }}
              </v-list-item>
              <v-list-item prepend-icon="mdi-check" class="text-success">
                {{ $t('admin.poolGuide.bp2') }}
              </v-list-item>
              <v-list-item prepend-icon="mdi-check" class="text-success">
                {{ $t('admin.poolGuide.bp3') }}
              </v-list-item>
              <v-list-item prepend-icon="mdi-check" class="text-success">
                {{ $t('admin.poolGuide.bp4') }}
              </v-list-item>
              <v-list-item prepend-icon="mdi-close" class="text-error">
                {{ $t('admin.poolGuide.bpAvoid') }}
              </v-list-item>
            </v-list>
          </v-tabs-window-item>

          <!-- Simulation Insights Tab -->
          <v-tabs-window-item value="insights">
            <v-alert type="info" variant="tonal" class="mb-4">
              <strong>{{ $t('admin.floatingPool.simulationInsights') }}</strong> {{ $t('admin.poolGuide.insightsDesc') }}
            </v-alert>

            <h4 class="mb-3">{{ $t('admin.poolGuide.understandingScenarios') }}</h4>
            <p class="mb-3">{{ $t('admin.poolGuide.scenariosDesc') }}</p>
            <v-table density="compact" class="mb-4">
              <thead>
                <tr>
                  <th>{{ $t('admin.poolGuide.scenario') }}</th>
                  <th>{{ $t('common.meaning') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><strong>{{ $t('admin.poolGuide.scenarioCurrent') }}</strong></td>
                  <td>{{ $t('admin.poolGuide.scenarioCurrentDesc') }}</td>
                </tr>
                <tr>
                  <td><strong>{{ $t('admin.poolGuide.scenarioMinimum') }}</strong></td>
                  <td>{{ $t('admin.poolGuide.scenarioMinimumDesc') }}</td>
                </tr>
                <tr>
                  <td><strong>{{ $t('admin.poolGuide.scenarioOptimal') }}</strong></td>
                  <td>{{ $t('admin.poolGuide.scenarioOptimalDesc') }}</td>
                </tr>
                <tr>
                  <td><strong>{{ $t('admin.poolGuide.scenarioMaximum') }}</strong></td>
                  <td>{{ $t('admin.poolGuide.scenarioMaximumDesc') }}</td>
                </tr>
              </tbody>
            </v-table>

            <h4 class="mb-3">{{ $t('admin.poolGuide.readingRecommendations') }}</h4>
            <v-list density="compact">
              <v-list-item>
                <template #prepend>
                  <v-chip size="small" color="warning">{{ $t('admin.poolGuide.highPriority') }}</v-chip>
                </template>
                <v-list-item-subtitle>{{ $t('admin.poolGuide.highPriorityDesc') }}</v-list-item-subtitle>
              </v-list-item>
              <v-list-item>
                <template #prepend>
                  <v-chip size="small" color="info">{{ $t('admin.poolGuide.mediumPriority') }}</v-chip>
                </template>
                <v-list-item-subtitle>{{ $t('admin.poolGuide.mediumPriorityDesc') }}</v-list-item-subtitle>
              </v-list-item>
              <v-list-item>
                <template #prepend>
                  <v-chip size="small" color="success">{{ $t('admin.poolGuide.lowPriority') }}</v-chip>
                </template>
                <v-list-item-subtitle>{{ $t('admin.poolGuide.lowPriorityDesc') }}</v-list-item-subtitle>
              </v-list-item>
            </v-list>

            <v-divider class="my-4" />

            <v-alert type="success" variant="tonal">
              <strong>{{ $t('admin.poolGuide.tip') }}:</strong> {{ $t('admin.poolGuide.tipText') }}
            </v-alert>
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
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

defineProps({
  modelValue: {
    type: Boolean,
    default: false
  }
})

defineEmits(['update:modelValue'])

const guideTab = ref('overview')

const stepperAssign = computed(() => [
  t('common.select'),
  t('admin.poolGuide.stepConfigure'),
  t('common.confirm')
])
</script>
