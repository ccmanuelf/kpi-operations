<template>
  <v-card>
    <v-card-title class="d-flex align-center">
      <v-icon start>mdi-calendar-clock</v-icon>
      Production Schedule
      <v-spacer />
      <v-chip
        v-if="store.activeSchedule"
        :color="getScheduleStatusColor(store.activeSchedule.status)"
        variant="tonal"
        class="mr-2"
      >
        {{ store.activeSchedule.status }}
      </v-chip>
      <v-btn
        color="primary"
        size="small"
        variant="elevated"
        :loading="store.isGeneratingSchedule"
        @click="showGenerateDialog = true"
      >
        <v-icon start>mdi-plus</v-icon>
        Generate Schedule
      </v-btn>
      <v-btn
        v-if="store.activeSchedule && store.activeSchedule.status !== 'COMMITTED'"
        color="success"
        size="small"
        variant="elevated"
        class="ml-2"
        @click="store.showScheduleCommitDialog = true"
      >
        <v-icon start>mdi-check</v-icon>
        Commit Schedule
      </v-btn>
    </v-card-title>
    <v-card-text>
      <!-- Active Schedule Info -->
      <v-card v-if="store.activeSchedule" variant="outlined" class="mb-4">
        <v-card-text>
          <v-row>
            <v-col cols="3">
              <div class="text-caption text-grey">Schedule Name</div>
              <div class="text-subtitle-1 font-weight-bold">{{ store.activeSchedule.name }}</div>
            </v-col>
            <v-col cols="3">
              <div class="text-caption text-grey">Start Date</div>
              <div class="text-subtitle-1">{{ store.activeSchedule.start_date }}</div>
            </v-col>
            <v-col cols="3">
              <div class="text-caption text-grey">End Date</div>
              <div class="text-subtitle-1">{{ store.activeSchedule.end_date }}</div>
            </v-col>
            <v-col cols="3">
              <div class="text-caption text-grey">Total Orders</div>
              <div class="text-subtitle-1">{{ schedule.length }}</div>
            </v-col>
          </v-row>
        </v-card-text>
      </v-card>

      <!-- Schedule Table -->
      <v-data-table
        v-if="schedule.length"
        :headers="headers"
        :items="schedule"
        :items-per-page="15"
        :group-by="[{ key: 'scheduled_date', order: 'asc' }]"
        class="elevation-1"
        density="compact"
      >
        <template v-slot:group-header="{ item, columns, toggleGroup, isGroupOpen }">
          <tr class="bg-grey-lighten-3">
            <td :colspan="columns.length">
              <v-btn
                :icon="isGroupOpen(item) ? 'mdi-chevron-down' : 'mdi-chevron-right'"
                size="small"
                variant="text"
                @click="toggleGroup(item)"
              />
              <strong>{{ formatDate(item.value) }}</strong>
              <v-chip size="small" class="ml-2">
                {{ item.items.length }} orders
              </v-chip>
            </td>
          </tr>
        </template>

        <template v-slot:item.status="{ item }">
          <v-chip
            :color="getDetailStatusColor(item.status)"
            size="small"
            variant="tonal"
          >
            {{ item.status }}
          </v-chip>
        </template>

        <template v-slot:item.planned_quantity="{ item }">
          {{ item.planned_quantity?.toLocaleString() }}
        </template>

        <template v-slot:item.sequence_number="{ item, index }">
          <div class="d-flex align-center">
            <span class="mr-2">{{ item.sequence_number }}</span>
            <v-btn
              icon="mdi-arrow-up"
              size="x-small"
              variant="text"
              :disabled="index === 0"
              @click="moveUp(index)"
            />
            <v-btn
              icon="mdi-arrow-down"
              size="x-small"
              variant="text"
              :disabled="index === schedule.length - 1"
              @click="moveDown(index)"
            />
          </div>
        </template>
      </v-data-table>

      <!-- Empty State -->
      <div v-else class="text-center pa-8 text-grey">
        <v-icon size="64" color="grey-lighten-1">mdi-calendar-clock</v-icon>
        <div class="text-h6 mt-4">No Production Schedule</div>
        <div class="text-body-2 mt-2">
          Click "Generate Schedule" to create a production schedule based on your orders and capacity.
        </div>
        <v-btn
          color="primary"
          variant="tonal"
          class="mt-4"
          @click="showGenerateDialog = true"
        >
          Generate Schedule
        </v-btn>
      </div>
    </v-card-text>

    <!-- Generate Schedule Dialog -->
    <v-dialog v-model="showGenerateDialog" max-width="500">
      <v-card>
        <v-card-title>Generate Production Schedule</v-card-title>
        <v-card-text>
          <v-text-field
            v-model="scheduleName"
            label="Schedule Name"
            variant="outlined"
            class="mb-2"
          />
          <v-row>
            <v-col cols="6">
              <v-text-field
                v-model="startDate"
                label="Start Date"
                type="date"
                variant="outlined"
              />
            </v-col>
            <v-col cols="6">
              <v-text-field
                v-model="endDate"
                label="End Date"
                type="date"
                variant="outlined"
              />
            </v-col>
          </v-row>
          <v-checkbox
            v-model="includeAllOrders"
            label="Include all pending orders"
            hide-details
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="showGenerateDialog = false">Cancel</v-btn>
          <v-btn
            color="primary"
            :loading="store.isGeneratingSchedule"
            @click="generateSchedule"
          >
            Generate
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script setup>
/**
 * SchedulePanel - Generates and manages production schedules.
 *
 * Creates production schedules from pending orders, displaying schedule
 * details grouped by date with sequence reordering controls. Supports
 * schedule generation with configurable name and date range, status tracking
 * (DRAFT, GENERATED, COMMITTED), and schedule commitment workflow.
 *
 * Store dependency: useCapacityPlanningStore (worksheets.productionSchedule, activeSchedule)
 * No props or emits -- all state managed via store.
 */
import { ref, computed, onMounted } from 'vue'
import { useCapacityPlanningStore } from '@/stores/capacityPlanningStore'

const store = useCapacityPlanningStore()

const showGenerateDialog = ref(false)
const scheduleName = ref('')
const startDate = ref('')
const endDate = ref('')
const includeAllOrders = ref(true)

const headers = [
  { title: 'Sequence', key: 'sequence_number', width: '100px' },
  { title: 'Order #', key: 'order_number', width: '120px' },
  { title: 'Line', key: 'line_code', width: '100px' },
  { title: 'Date', key: 'scheduled_date', width: '120px' },
  { title: 'Quantity', key: 'planned_quantity', width: '100px' },
  { title: 'Status', key: 'status', width: '100px' }
]

const schedule = computed(() => store.worksheets.productionSchedule.data)

const getScheduleStatusColor = (status) => {
  const colors = {
    DRAFT: 'grey',
    GENERATED: 'blue',
    COMMITTED: 'success',
    IN_PROGRESS: 'orange',
    COMPLETED: 'green'
  }
  return colors[status] || 'grey'
}

const getDetailStatusColor = (status) => {
  const colors = {
    SCHEDULED: 'blue',
    IN_PROGRESS: 'orange',
    COMPLETED: 'success',
    DELAYED: 'error'
  }
  return colors[status] || 'grey'
}

const formatDate = (date) => {
  if (!date) return ''
  return new Date(date).toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric'
  })
}

const generateSchedule = async () => {
  showGenerateDialog.value = false
  try {
    await store.generateSchedule(
      scheduleName.value || `Schedule ${new Date().toLocaleDateString()}`,
      startDate.value,
      endDate.value,
      includeAllOrders.value ? null : []
    )
  } catch (error) {
    console.error('Schedule generation failed:', error)
  }
}

const moveUp = (index) => {
  if (index > 0) {
    const items = schedule.value
    const temp = items[index].sequence_number
    items[index].sequence_number = items[index - 1].sequence_number
    items[index - 1].sequence_number = temp
    store.worksheets.productionSchedule.dirty = true
  }
}

const moveDown = (index) => {
  if (index < schedule.value.length - 1) {
    const items = schedule.value
    const temp = items[index].sequence_number
    items[index].sequence_number = items[index + 1].sequence_number
    items[index + 1].sequence_number = temp
    store.worksheets.productionSchedule.dirty = true
  }
}

onMounted(() => {
  const today = new Date()
  const thirtyDaysLater = new Date(today)
  thirtyDaysLater.setDate(thirtyDaysLater.getDate() + 30)

  startDate.value = today.toISOString().slice(0, 10)
  endDate.value = thirtyDaysLater.toISOString().slice(0, 10)
  scheduleName.value = `Schedule ${today.toLocaleDateString()}`
})
</script>
