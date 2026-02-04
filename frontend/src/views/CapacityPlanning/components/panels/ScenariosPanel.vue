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
          <div v-if="newScenario.type === 'overtime'">
            <v-text-field
              v-model.number="newScenario.parameters.overtime_hours"
              label="Additional Overtime Hours per Day"
              type="number"
              variant="outlined"
            />
          </div>
          <div v-else-if="newScenario.type === 'line_add'">
            <v-text-field
              v-model.number="newScenario.parameters.additional_lines"
              label="Number of Additional Lines"
              type="number"
              variant="outlined"
            />
            <v-text-field
              v-model.number="newScenario.parameters.capacity_per_line"
              label="Capacity per Line (units/hour)"
              type="number"
              variant="outlined"
            />
          </div>
          <div v-else-if="newScenario.type === 'rush_order'">
            <v-text-field
              v-model="newScenario.parameters.order_number"
              label="Rush Order Number"
              variant="outlined"
            />
            <v-text-field
              v-model.number="newScenario.parameters.priority_boost"
              label="Priority Boost"
              type="number"
              variant="outlined"
            />
          </div>
          <div v-else-if="newScenario.type === 'capacity'">
            <v-text-field
              v-model.number="newScenario.parameters.efficiency_change"
              label="Efficiency Change (%)"
              type="number"
              variant="outlined"
              hint="Positive to increase, negative to decrease"
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
import { ref, computed, reactive } from 'vue'
import { useCapacityPlanningStore } from '@/stores/capacityPlanningStore'

const store = useCapacityPlanningStore()

const showCreateDialog = ref(false)
const selectedScenarios = ref([])

const newScenario = reactive({
  name: '',
  type: 'capacity',
  parameters: {}
})

const scenarioTypes = [
  { text: 'Capacity Change', value: 'capacity' },
  { text: 'Overtime', value: 'overtime' },
  { text: 'Add Production Line', value: 'line_add' },
  { text: 'Rush Order', value: 'rush_order' }
]

const scenarios = computed(() => store.worksheets.whatIfScenarios.data)

const getTypeColor = (type) => {
  const colors = {
    capacity: 'blue',
    overtime: 'orange',
    line_add: 'green',
    rush_order: 'purple'
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
    newScenario.type = 'capacity'
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
