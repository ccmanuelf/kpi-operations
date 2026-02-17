<template>
  <v-card>
    <v-card-title class="d-flex align-center">
      <v-icon start>mdi-help-rhombus</v-icon>
      {{ t('capacityPlanning.scenarios.title') }}
      <v-spacer />
      <v-btn
        color="primary"
        size="small"
        variant="elevated"
        :loading="store.isCreatingScenario"
        @click="showCreateDialog = true"
      >
        <v-icon start>mdi-plus</v-icon>
        {{ t('capacityPlanning.scenarios.createScenario') }}
      </v-btn>
      <v-btn
        v-if="selectedScenarios.length >= 2"
        color="info"
        size="small"
        variant="outlined"
        class="ml-2"
        @click="compareScenarios"
      >
        <v-icon start>mdi-compare</v-icon>
        {{ t('capacityPlanning.scenarios.compareCount', { count: selectedScenarios.length }) }}
      </v-btn>
    </v-card-title>
    <v-card-text>
      <!-- Scenario Cards -->
      <v-row v-if="scenarios.length">
        <v-col
          v-for="scenario in scenarios"
          :key="scenario._id"
          cols="12"
          md="6"
          lg="4"
        >
          <v-card
            :variant="selectedScenarios.includes(scenario._id) ? 'elevated' : 'outlined'"
            :class="selectedScenarios.includes(scenario._id) ? 'border-primary' : ''"
          >
            <v-card-title class="d-flex align-center">
              <v-checkbox
                :model-value="selectedScenarios.includes(scenario._id)"
                hide-details
                density="compact"
                class="mr-2"
                @update:modelValue="toggleSelection(scenario._id)"
              />
              {{ scenario.scenario_name }}
              <v-spacer />
              <v-chip
                :color="getTypeColor(scenario.scenario_type)"
                size="small"
                variant="tonal"
              >
                {{ scenario.scenario_type }}
              </v-chip>
            </v-card-title>
            <v-card-text>
              <div class="mb-2">
                <span class="text-caption text-grey">{{ t('capacityPlanning.scenarios.statusLabel') }}</span>
                <v-chip
                  :color="getStatusColor(scenario.status)"
                  size="x-small"
                  class="ml-2"
                >
                  {{ scenario.status }}
                </v-chip>
              </div>
              <div v-if="scenario.parameters" class="text-body-2">
                <div v-for="(value, key) in scenario.parameters" :key="key">
                  <strong>{{ formatParamName(key) }}:</strong> {{ value }}
                </div>
              </div>
              <div v-if="scenario.results" class="mt-2">
                <v-divider class="my-2" />
                <div class="text-caption text-grey mb-1">{{ t('capacityPlanning.scenarios.resultsLabel') }}</div>
                <div class="text-body-2">
                  <div>{{ t('capacityPlanning.scenarios.totalOutput') }}: {{ scenario.results.total_output?.toLocaleString() || t('common.na') }}</div>
                  <div>{{ t('capacityPlanning.scenarios.utilization') }}: {{ scenario.results.avg_utilization?.toFixed(1) || t('common.na') }}%</div>
                  <div>{{ t('capacityPlanning.scenarios.onTime') }}: {{ scenario.results.on_time_rate?.toFixed(1) || t('common.na') }}%</div>
                </div>
              </div>
            </v-card-text>
            <v-card-actions>
              <v-btn
                v-if="scenario.status === 'DRAFT'"
                color="primary"
                size="small"
                variant="tonal"
                @click="runScenario(scenario)"
              >
                <v-icon start>mdi-play</v-icon>
                {{ t('capacityPlanning.scenarios.evaluate') }}
              </v-btn>
              <v-btn
                v-if="scenario.status === 'EVALUATED'"
                color="success"
                size="small"
                variant="tonal"
                @click="applyScenario(scenario)"
              >
                <v-icon start>mdi-check</v-icon>
                {{ t('capacityPlanning.scenarios.apply') }}
              </v-btn>
              <v-spacer />
              <v-btn
                color="error"
                size="small"
                variant="text"
                @click="deleteScenario(scenario)"
              >
                <v-icon>mdi-delete</v-icon>
              </v-btn>
            </v-card-actions>
          </v-card>
        </v-col>
      </v-row>

      <!-- Empty State -->
      <div v-else class="text-center pa-8 text-grey">
        <v-icon size="64" color="grey-lighten-1">mdi-help-rhombus</v-icon>
        <div class="text-h6 mt-4">{{ t('capacityPlanning.scenarios.noScenariosTitle') }}</div>
        <div class="text-body-2 mt-2">
          {{ t('capacityPlanning.scenarios.noScenariosDescription') }}
        </div>
        <v-btn
          color="primary"
          variant="tonal"
          class="mt-4"
          @click="showCreateDialog = true"
        >
          {{ t('capacityPlanning.scenarios.createScenario') }}
        </v-btn>
      </div>
    </v-card-text>

    <!-- Create Scenario Dialog -->
    <v-dialog v-model="showCreateDialog" max-width="600">
      <v-card>
        <v-card-title>{{ t('capacityPlanning.scenarios.createDialogTitle') }}</v-card-title>
        <v-card-text>
          <v-text-field
            v-model="newScenario.name"
            :label="t('capacityPlanning.scenarios.scenarioName')"
            variant="outlined"
            class="mb-2"
          />
          <v-select
            v-model="newScenario.type"
            :items="scenarioTypes"
            item-title="text"
            item-value="value"
            :label="t('capacityPlanning.scenarios.scenarioType')"
            variant="outlined"
            class="mb-2"
          />

          <!-- Type-specific parameters -->
          <div v-if="newScenario.type === 'OVERTIME'">
            <v-text-field
              v-model.number="newScenario.parameters.overtime_percent"
              :label="t('capacityPlanning.scenarios.params.overtimePercent')"
              type="number"
              variant="outlined"
              hint="Default: 20%"
            />
          </div>
          <div v-else-if="newScenario.type === 'SETUP_REDUCTION'">
            <v-text-field
              v-model.number="newScenario.parameters.reduction_percent"
              :label="t('capacityPlanning.scenarios.params.reductionPercent')"
              type="number"
              variant="outlined"
              hint="Default: 30%"
            />
          </div>
          <div v-else-if="newScenario.type === 'SUBCONTRACT'">
            <v-text-field
              v-model.number="newScenario.parameters.subcontract_percent"
              :label="t('capacityPlanning.scenarios.params.subcontractPercent')"
              type="number"
              variant="outlined"
              hint="Default: 40%"
            />
            <v-text-field
              v-model="newScenario.parameters.department"
              :label="t('capacityPlanning.scenarios.params.department')"
              variant="outlined"
              hint="Default: CUTTING"
            />
          </div>
          <div v-else-if="newScenario.type === 'NEW_LINE'">
            <v-text-field
              v-model="newScenario.parameters.new_line_code"
              :label="t('capacityPlanning.scenarios.params.newLineCode')"
              variant="outlined"
              hint="Default: SEWING_NEW"
            />
            <v-text-field
              v-model.number="newScenario.parameters.operators"
              :label="t('capacityPlanning.scenarios.params.operators')"
              type="number"
              variant="outlined"
              hint="Default: 12"
            />
          </div>
          <div v-else-if="newScenario.type === 'THREE_SHIFT'">
            <v-text-field
              v-model.number="newScenario.parameters.shift3_hours"
              :label="t('capacityPlanning.scenarios.params.shift3Hours')"
              type="number"
              variant="outlined"
              hint="Default: 8.0"
            />
            <v-text-field
              v-model.number="newScenario.parameters.shift3_efficiency"
              :label="t('capacityPlanning.scenarios.params.shift3Efficiency')"
              type="number"
              step="0.05"
              variant="outlined"
              hint="Default: 0.80"
            />
          </div>
          <div v-else-if="newScenario.type === 'LEAD_TIME_DELAY'">
            <v-text-field
              v-model.number="newScenario.parameters.delay_days"
              :label="t('capacityPlanning.scenarios.params.delayDays')"
              type="number"
              variant="outlined"
              hint="Default: 7"
            />
          </div>
          <div v-else-if="newScenario.type === 'ABSENTEEISM_SPIKE'">
            <v-text-field
              v-model.number="newScenario.parameters.absenteeism_percent"
              :label="t('capacityPlanning.scenarios.params.absenteeismPercent')"
              type="number"
              variant="outlined"
              hint="Default: 15%"
            />
            <v-text-field
              v-model.number="newScenario.parameters.duration_days"
              :label="t('capacityPlanning.scenarios.params.durationDays')"
              type="number"
              variant="outlined"
              hint="Default: 5"
            />
          </div>
          <div v-else-if="newScenario.type === 'MULTI_CONSTRAINT'">
            <v-text-field
              v-model.number="newScenario.parameters.overtime_percent"
              :label="t('capacityPlanning.scenarios.params.overtimePercentMulti')"
              type="number"
              variant="outlined"
              hint="Default: 10%"
            />
            <v-text-field
              v-model.number="newScenario.parameters.setup_reduction_percent"
              :label="t('capacityPlanning.scenarios.params.setupReductionPercent')"
              type="number"
              variant="outlined"
              hint="Default: 15%"
            />
            <v-text-field
              v-model.number="newScenario.parameters.absenteeism_percent"
              :label="t('capacityPlanning.scenarios.params.absenteeismPercentMulti')"
              type="number"
              variant="outlined"
              hint="Default: 8%"
            />
          </div>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="showCreateDialog = false">{{ t('common.cancel') }}</v-btn>
          <v-btn
            color="primary"
            :loading="store.isCreatingScenario"
            @click="createScenario"
          >
            {{ t('capacityPlanning.scenarios.create') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script setup>
/**
 * ScenariosPanel - What-if scenario creation, evaluation, and comparison.
 *
 * Supports 8 scenario types: OVERTIME, SETUP_REDUCTION, SUBCONTRACT, NEW_LINE,
 * THREE_SHIFT, LEAD_TIME_DELAY, ABSENTEEISM_SPIKE, MULTI_CONSTRAINT. Each type
 * has dedicated parameter inputs. Scenarios progress through DRAFT -> EVALUATED
 * -> APPLIED/REJECTED workflow. Multi-select enables side-by-side comparison
 * of evaluated scenarios.
 *
 * Store dependency: useCapacityPlanningStore (worksheets.whatIfScenarios)
 * No props or emits -- all state managed via store.
 */
import { ref, computed, reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import { useCapacityPlanningStore } from '@/stores/capacityPlanningStore'
import { useNotificationStore } from '@/stores/notificationStore'

const { t } = useI18n()

const store = useCapacityPlanningStore()
const notificationStore = useNotificationStore()

const showCreateDialog = ref(false)
const selectedScenarios = ref([])

const newScenario = reactive({
  name: '',
  type: 'OVERTIME',
  parameters: {}
})

const scenarioTypes = computed(() => [
  { text: t('capacityPlanning.scenarios.types.overtime'), value: 'OVERTIME' },
  { text: t('capacityPlanning.scenarios.types.setupReduction'), value: 'SETUP_REDUCTION' },
  { text: t('capacityPlanning.scenarios.types.subcontract'), value: 'SUBCONTRACT' },
  { text: t('capacityPlanning.scenarios.types.newLine'), value: 'NEW_LINE' },
  { text: t('capacityPlanning.scenarios.types.threeShift'), value: 'THREE_SHIFT' },
  { text: t('capacityPlanning.scenarios.types.leadTimeDelay'), value: 'LEAD_TIME_DELAY' },
  { text: t('capacityPlanning.scenarios.types.absenteeismSpike'), value: 'ABSENTEEISM_SPIKE' },
  { text: t('capacityPlanning.scenarios.types.multiConstraint'), value: 'MULTI_CONSTRAINT' }
])

const scenarios = computed(() => store.worksheets.whatIfScenarios.data)

const getTypeColor = (type) => {
  const colors = {
    OVERTIME: 'orange',
    SETUP_REDUCTION: 'teal',
    SUBCONTRACT: 'indigo',
    NEW_LINE: 'green',
    THREE_SHIFT: 'deep-purple',
    LEAD_TIME_DELAY: 'red',
    ABSENTEEISM_SPIKE: 'amber',
    MULTI_CONSTRAINT: 'blue'
  }
  return colors[type] || 'grey'
}

const getStatusColor = (status) => {
  const colors = {
    DRAFT: 'grey',
    EVALUATED: 'success',
    APPLIED: 'primary',
    REJECTED: 'error'
  }
  return colors[status] || 'grey'
}

const formatParamName = (key) => {
  return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

const toggleSelection = (id) => {
  const idx = selectedScenarios.value.indexOf(id)
  if (idx === -1) {
    selectedScenarios.value.push(id)
  } else {
    selectedScenarios.value.splice(idx, 1)
  }
}

const createScenario = async () => {
  showCreateDialog.value = false
  try {
    await store.createScenario(
      newScenario.name || 'New Scenario',
      newScenario.type,
      { ...newScenario.parameters }
    )
    // Reset form
    newScenario.name = ''
    newScenario.type = 'OVERTIME'
    newScenario.parameters = {}
  } catch (error) {
    console.error('Failed to create scenario:', error)
  }
}

const runScenario = async (scenario) => {
  try {
    await store.runScenario(scenario.id || scenario._id)
  } catch (error) {
    console.error('Failed to run scenario:', error)
    notificationStore.showError(error.message || 'Failed to run scenario')
  }
}

const applyScenario = (scenario) => {
  // TODO: Apply scenario to main schedule
  console.log('Applying scenario:', scenario)
  notificationStore.showInfo('Apply scenario is not yet implemented')
}

const deleteScenario = async (scenario) => {
  try {
    await store.deleteScenario(scenario.id || scenario._id)
  } catch (error) {
    console.error('Failed to delete scenario:', error)
    notificationStore.showError(error.message || 'Failed to delete scenario')
  }
}

const compareScenarios = async () => {
  try {
    await store.compareScenarios(selectedScenarios.value)
  } catch (error) {
    console.error('Failed to compare scenarios:', error)
  }
}
</script>
