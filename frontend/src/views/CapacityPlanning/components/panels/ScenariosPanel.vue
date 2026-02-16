<template>
  <v-card>
    <v-card-title class="d-flex align-center">
      <v-icon start>mdi-help-rhombus</v-icon>
      What-If Scenarios
      <v-spacer />
      <v-btn
        color="primary"
        size="small"
        variant="elevated"
        :loading="store.isCreatingScenario"
        @click="showCreateDialog = true"
      >
        <v-icon start>mdi-plus</v-icon>
        Create Scenario
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
        Compare ({{ selectedScenarios.length }})
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
                <span class="text-caption text-grey">Status:</span>
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
                <div class="text-caption text-grey mb-1">Results:</div>
                <div class="text-body-2">
                  <div>Total Output: {{ scenario.results.total_output?.toLocaleString() || 'N/A' }}</div>
                  <div>Utilization: {{ scenario.results.avg_utilization?.toFixed(1) || 'N/A' }}%</div>
                  <div>On-Time: {{ scenario.results.on_time_rate?.toFixed(1) || 'N/A' }}%</div>
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
                Evaluate
              </v-btn>
              <v-btn
                v-if="scenario.status === 'EVALUATED'"
                color="success"
                size="small"
                variant="tonal"
                @click="applyScenario(scenario)"
              >
                <v-icon start>mdi-check</v-icon>
                Apply
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
        <div class="text-h6 mt-4">No Scenarios Created</div>
        <div class="text-body-2 mt-2">
          Create what-if scenarios to evaluate different planning options like overtime, adding lines, or rush orders.
        </div>
        <v-btn
          color="primary"
          variant="tonal"
          class="mt-4"
          @click="showCreateDialog = true"
        >
          Create Scenario
        </v-btn>
      </div>
    </v-card-text>

    <!-- Create Scenario Dialog -->
    <v-dialog v-model="showCreateDialog" max-width="600">
      <v-card>
        <v-card-title>Create What-If Scenario</v-card-title>
        <v-card-text>
          <v-text-field
            v-model="newScenario.name"
            label="Scenario Name"
            variant="outlined"
            class="mb-2"
          />
          <v-select
            v-model="newScenario.type"
            :items="scenarioTypes"
            item-title="text"
            item-value="value"
            label="Scenario Type"
            variant="outlined"
            class="mb-2"
          />

          <!-- Type-specific parameters -->
          <div v-if="newScenario.type === 'OVERTIME'">
            <v-text-field
              v-model.number="newScenario.parameters.overtime_percent"
              label="Overtime Increase (%)"
              type="number"
              variant="outlined"
              hint="Default: 20%"
            />
          </div>
          <div v-else-if="newScenario.type === 'SETUP_REDUCTION'">
            <v-text-field
              v-model.number="newScenario.parameters.reduction_percent"
              label="Setup Time Reduction (%)"
              type="number"
              variant="outlined"
              hint="Default: 30%"
            />
          </div>
          <div v-else-if="newScenario.type === 'SUBCONTRACT'">
            <v-text-field
              v-model.number="newScenario.parameters.subcontract_percent"
              label="Subcontract Percentage (%)"
              type="number"
              variant="outlined"
              hint="Default: 40%"
            />
            <v-text-field
              v-model="newScenario.parameters.department"
              label="Department to Subcontract"
              variant="outlined"
              hint="Default: CUTTING"
            />
          </div>
          <div v-else-if="newScenario.type === 'NEW_LINE'">
            <v-text-field
              v-model="newScenario.parameters.new_line_code"
              label="New Line Code"
              variant="outlined"
              hint="Default: SEWING_NEW"
            />
            <v-text-field
              v-model.number="newScenario.parameters.operators"
              label="Number of Operators"
              type="number"
              variant="outlined"
              hint="Default: 12"
            />
          </div>
          <div v-else-if="newScenario.type === 'THREE_SHIFT'">
            <v-text-field
              v-model.number="newScenario.parameters.shift3_hours"
              label="Third Shift Hours"
              type="number"
              variant="outlined"
              hint="Default: 8.0"
            />
            <v-text-field
              v-model.number="newScenario.parameters.shift3_efficiency"
              label="Night Shift Efficiency (0-1)"
              type="number"
              step="0.05"
              variant="outlined"
              hint="Default: 0.80"
            />
          </div>
          <div v-else-if="newScenario.type === 'LEAD_TIME_DELAY'">
            <v-text-field
              v-model.number="newScenario.parameters.delay_days"
              label="Delay Duration (days)"
              type="number"
              variant="outlined"
              hint="Default: 7"
            />
          </div>
          <div v-else-if="newScenario.type === 'ABSENTEEISM_SPIKE'">
            <v-text-field
              v-model.number="newScenario.parameters.absenteeism_percent"
              label="Absenteeism Rate (%)"
              type="number"
              variant="outlined"
              hint="Default: 15%"
            />
            <v-text-field
              v-model.number="newScenario.parameters.duration_days"
              label="Duration (days)"
              type="number"
              variant="outlined"
              hint="Default: 5"
            />
          </div>
          <div v-else-if="newScenario.type === 'MULTI_CONSTRAINT'">
            <v-text-field
              v-model.number="newScenario.parameters.overtime_percent"
              label="Overtime (%)"
              type="number"
              variant="outlined"
              hint="Default: 10%"
            />
            <v-text-field
              v-model.number="newScenario.parameters.setup_reduction_percent"
              label="Setup Reduction (%)"
              type="number"
              variant="outlined"
              hint="Default: 15%"
            />
            <v-text-field
              v-model.number="newScenario.parameters.absenteeism_percent"
              label="Absenteeism (%)"
              type="number"
              variant="outlined"
              hint="Default: 8%"
            />
          </div>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="showCreateDialog = false">Cancel</v-btn>
          <v-btn
            color="primary"
            :loading="store.isCreatingScenario"
            @click="createScenario"
          >
            Create
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
import { useCapacityPlanningStore } from '@/stores/capacityPlanningStore'

const store = useCapacityPlanningStore()

const showCreateDialog = ref(false)
const selectedScenarios = ref([])

const newScenario = reactive({
  name: '',
  type: 'OVERTIME',
  parameters: {}
})

const scenarioTypes = [
  { text: 'Overtime +20%', value: 'OVERTIME' },
  { text: 'Setup Time Reduction -30%', value: 'SETUP_REDUCTION' },
  { text: 'Subcontract Cutting 40%', value: 'SUBCONTRACT' },
  { text: 'New Sewing Line', value: 'NEW_LINE' },
  { text: '3-Shift Operation', value: 'THREE_SHIFT' },
  { text: 'Material Lead Time Delay', value: 'LEAD_TIME_DELAY' },
  { text: 'Absenteeism Spike 15%', value: 'ABSENTEEISM_SPIKE' },
  { text: 'Multi-Constraint Combined', value: 'MULTI_CONSTRAINT' }
]

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
  }
}

const applyScenario = (scenario) => {
  // TODO: Apply scenario to main schedule
  console.log('Applying scenario:', scenario)
}

const deleteScenario = async (scenario) => {
  try {
    await store.deleteScenario(scenario.id || scenario._id)
  } catch (error) {
    console.error('Failed to delete scenario:', error)
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
