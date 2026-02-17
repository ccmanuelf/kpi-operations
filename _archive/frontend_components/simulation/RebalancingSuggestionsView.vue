<template>
  <div class="rebalancing-suggestions-view">
    <!-- Well Balanced State -->
    <v-alert
      v-if="suggestions.length === 0"
      type="success"
      variant="tonal"
      prominent
      class="mb-4"
    >
      <template v-slot:prepend>
        <v-icon size="large">mdi-check-circle</v-icon>
      </template>
      <div class="text-h6">Line is Well Balanced</div>
      <div class="text-body-2">
        No rebalancing recommendations at this time. All stations are operating within acceptable
        utilization ranges and no bottlenecks were detected.
      </div>
    </v-alert>

    <template v-else>
      <!-- Summary Cards -->
      <v-row class="mb-4">
        <v-col cols="12" md="6">
          <v-card variant="tonal" color="error">
            <v-card-text>
              <div class="d-flex align-center">
                <v-avatar color="error" size="48" class="mr-4">
                  <v-icon color="white">mdi-alert-circle</v-icon>
                </v-avatar>
                <div>
                  <div class="text-h5 font-weight-bold">{{ bottleneckCount }}</div>
                  <div class="text-body-2">Bottleneck Operations</div>
                  <div class="text-caption">Need additional operators</div>
                </div>
              </div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" md="6">
          <v-card variant="tonal" color="success">
            <v-card-text>
              <div class="d-flex align-center">
                <v-avatar color="success" size="48" class="mr-4">
                  <v-icon color="white">mdi-account-arrow-right</v-icon>
                </v-avatar>
                <div>
                  <div class="text-h5 font-weight-bold">{{ donorCount }}</div>
                  <div class="text-body-2">Donor Operations</div>
                  <div class="text-caption">Can share operators</div>
                </div>
              </div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <!-- Instructions -->
      <v-alert type="info" variant="tonal" density="compact" class="mb-4">
        <v-icon start>mdi-lightbulb</v-icon>
        <strong>How to use:</strong> Move operators from donor stations (green, low utilization)
        to bottleneck stations (red, high utilization) to balance the line.
      </v-alert>

      <!-- Suggestions List -->
      <v-card variant="outlined">
        <v-card-title class="d-flex align-center">
          <v-icon class="mr-2">mdi-swap-horizontal</v-icon>
          Rebalancing Suggestions
          <v-spacer />
          <v-chip size="small" :color="suggestions.length > 0 ? 'warning' : 'success'">
            {{ suggestions.length }} suggestion{{ suggestions.length !== 1 ? 's' : '' }}
          </v-chip>
        </v-card-title>

        <v-data-table
          :headers="headers"
          :items="suggestions"
          density="comfortable"
          :items-per-page="10"
        >
          <!-- Role chip -->
          <template v-slot:item.role="{ item }">
            <v-chip
              :color="item.role === 'Bottleneck' ? 'error' : 'success'"
              size="small"
              variant="tonal"
            >
              <v-icon start size="small">
                {{ item.role === 'Bottleneck' ? 'mdi-alert-circle' : 'mdi-account-arrow-right' }}
              </v-icon>
              {{ item.role }}
            </v-chip>
          </template>

          <!-- Operators change -->
          <template v-slot:item.operators_before="{ item }">
            <div class="d-flex align-center">
              <span class="mr-2">{{ item.operators_before }}</span>
              <v-icon
                :color="item.role === 'Bottleneck' ? 'success' : 'warning'"
                size="small"
              >
                {{ item.role === 'Bottleneck' ? 'mdi-arrow-right' : 'mdi-arrow-left' }}
              </v-icon>
              <span class="ml-2 font-weight-bold" :class="getChangeClass(item)">
                {{ item.operators_after }}
              </span>
              <v-chip
                size="x-small"
                :color="item.role === 'Bottleneck' ? 'success' : 'warning'"
                variant="tonal"
                class="ml-2"
              >
                {{ item.role === 'Bottleneck' ? '+' : '' }}{{ item.operators_after - item.operators_before }}
              </v-chip>
            </div>
          </template>

          <!-- Utilization change -->
          <template v-slot:item.util_before_pct="{ item }">
            <div class="d-flex align-center">
              <v-progress-circular
                :model-value="item.util_before_pct"
                :color="getUtilColor(item.util_before_pct)"
                size="32"
                width="3"
              >
                <span class="text-caption">{{ Math.round(item.util_before_pct) }}</span>
              </v-progress-circular>
              <v-icon class="mx-2" size="small">mdi-arrow-right</v-icon>
              <v-progress-circular
                :model-value="item.util_after_pct"
                :color="getUtilColor(item.util_after_pct)"
                size="32"
                width="3"
              >
                <span class="text-caption">{{ Math.round(item.util_after_pct) }}</span>
              </v-progress-circular>
            </div>
          </template>

          <!-- Comment/Action -->
          <template v-slot:item.comment="{ item }">
            <div class="text-body-2">{{ item.comment }}</div>
          </template>
        </v-data-table>
      </v-card>

      <!-- Visual Flow Diagram -->
      <v-card variant="outlined" class="mt-4">
        <v-card-title>
          <v-icon class="mr-2">mdi-account-group</v-icon>
          Operator Flow Visualization
        </v-card-title>
        <v-card-text>
          <div class="flow-diagram">
            <!-- Donor stations -->
            <div class="flow-section donors">
              <div class="section-label text-success">
                <v-icon>mdi-arrow-up-circle</v-icon>
                Donors (Release Operators)
              </div>
              <div class="flow-items">
                <v-chip
                  v-for="donor in donorSuggestions"
                  :key="`donor-${donor.product}-${donor.step}`"
                  color="success"
                  variant="tonal"
                  class="ma-1"
                >
                  {{ donor.operation }}
                  <v-icon end size="small">mdi-account-minus</v-icon>
                  {{ donor.operators_before - donor.operators_after }}
                </v-chip>
              </div>
            </div>

            <!-- Arrow -->
            <div class="flow-arrow">
              <v-icon size="48" color="primary">mdi-arrow-down-bold</v-icon>
            </div>

            <!-- Bottleneck stations -->
            <div class="flow-section bottlenecks">
              <div class="section-label text-error">
                <v-icon>mdi-arrow-down-circle</v-icon>
                Bottlenecks (Receive Operators)
              </div>
              <div class="flow-items">
                <v-chip
                  v-for="bn in bottleneckSuggestions"
                  :key="`bn-${bn.product}-${bn.step}`"
                  color="error"
                  variant="tonal"
                  class="ma-1"
                >
                  {{ bn.operation }}
                  <v-icon end size="small">mdi-account-plus</v-icon>
                  +{{ bn.operators_after - bn.operators_before }}
                </v-chip>
              </div>
            </div>
          </div>
        </v-card-text>
      </v-card>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  suggestions: {
    type: Array,
    required: true,
    default: () => []
  }
})

// Table headers
const headers = [
  { title: 'Product', key: 'product', width: 100 },
  { title: 'Step', key: 'step', width: 60 },
  { title: 'Operation', key: 'operation' },
  { title: 'Machine', key: 'machine_tool' },
  { title: 'Role', key: 'role', width: 120 },
  { title: 'Operators Change', key: 'operators_before', width: 150 },
  { title: 'Utilization Change', key: 'util_before_pct', width: 150 },
  { title: 'Recommendation', key: 'comment' }
]

// Computed
const bottleneckCount = computed(() =>
  props.suggestions.filter(s => s.role === 'Bottleneck').length
)

const donorCount = computed(() =>
  props.suggestions.filter(s => s.role === 'Donor').length
)

const bottleneckSuggestions = computed(() =>
  props.suggestions.filter(s => s.role === 'Bottleneck')
)

const donorSuggestions = computed(() =>
  props.suggestions.filter(s => s.role === 'Donor')
)

// Helper functions
const getUtilColor = (util) => {
  if (util >= 95) return 'error'
  if (util >= 80) return 'warning'
  if (util <= 50) return 'info'
  return 'success'
}

const getChangeClass = (item) => {
  if (item.role === 'Bottleneck') return 'text-success'
  return 'text-warning'
}
</script>

<style scoped>
.rebalancing-suggestions-view {
  padding: 0;
}

.flow-diagram {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16px;
}

.flow-section {
  width: 100%;
  max-width: 600px;
  text-align: center;
  padding: 16px;
  border-radius: 8px;
  background: rgba(var(--v-theme-surface-variant), 0.3);
}

.flow-section.donors {
  border: 2px dashed rgba(var(--v-theme-success), 0.5);
}

.flow-section.bottlenecks {
  border: 2px dashed rgba(var(--v-theme-error), 0.5);
}

.section-label {
  font-weight: bold;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.flow-items {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
}

.flow-arrow {
  padding: 16px;
}
</style>
