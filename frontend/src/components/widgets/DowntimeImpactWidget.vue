<template>
  <v-card elevation="2">
    <v-card-title class="d-flex align-center bg-warning-darken-1 text-white">
      <v-icon class="mr-2" size="24">mdi-alert-circle</v-icon>
      Downtime Impact on OEE
      <v-spacer />
      <v-btn
        icon="mdi-refresh"
        variant="text"
        size="small"
        color="white"
        :loading="loading"
        @click="fetchData"
      />
    </v-card-title>

    <v-card-text class="pa-4">
      <!-- Loading State -->
      <div v-if="loading" class="d-flex justify-center align-center pa-8">
        <v-progress-circular indeterminate color="warning" />
      </div>

      <!-- Error State -->
      <v-alert
        v-else-if="error"
        type="error"
        variant="tonal"
        class="mb-0"
      >
        {{ error }}
      </v-alert>

      <!-- Empty State -->
      <div v-else-if="!downtimeRanking.length" class="text-center text-grey pa-8">
        <v-icon size="64" class="mb-4">mdi-checkbox-marked-circle-outline</v-icon>
        <div>No significant downtime events recorded</div>
      </div>

      <!-- Data Display -->
      <template v-else>
        <!-- OEE Impact Summary -->
        <div class="mb-4 pa-4 bg-grey-lighten-4 rounded">
          <v-row dense>
            <v-col cols="4" class="text-center">
              <div class="text-h5 font-weight-bold text-warning">{{ totalDowntimeHours }}h</div>
              <div class="text-caption text-grey">Total Downtime</div>
            </v-col>
            <v-col cols="4" class="text-center">
              <div class="text-h5 font-weight-bold text-error">-{{ totalOeeImpact }}%</div>
              <div class="text-caption text-grey">OEE Impact</div>
            </v-col>
            <v-col cols="4" class="text-center">
              <div class="text-h5 font-weight-bold text-info">{{ downtimeRanking.length }}</div>
              <div class="text-caption text-grey">Categories</div>
            </v-col>
          </v-row>
        </div>

        <!-- Downtime Categories List -->
        <v-list density="compact" class="pa-0">
          <v-list-item
            v-for="(item, index) in downtimeRanking"
            :key="item.category"
            class="mb-2"
          >
            <template v-slot:prepend>
              <v-avatar :color="getSeverityColor(item.severity)" size="36" class="mr-3">
                <span class="text-caption font-weight-bold text-white">{{ item.rank }}</span>
              </v-avatar>
            </template>

            <v-list-item-title class="font-weight-medium">
              {{ item.category }}
            </v-list-item-title>

            <v-list-item-subtitle class="d-flex align-center mt-1">
              <v-icon size="14" class="mr-1">mdi-clock-outline</v-icon>
              {{ item.totalHours }}h
              <v-divider vertical class="mx-2" />
              <v-icon size="14" class="mr-1">mdi-gauge</v-icon>
              <span :class="getImpactTextColor(item.oeeImpact)">
                -{{ item.oeeImpact }}% OEE
              </span>
              <v-divider vertical class="mx-2" />
              <v-icon size="14" class="mr-1">mdi-counter</v-icon>
              {{ item.eventCount }} events
            </v-list-item-subtitle>

            <template v-slot:append>
              <v-progress-linear
                :model-value="(item.totalHours / maxHours) * 100"
                :color="getSeverityColor(item.severity)"
                height="6"
                rounded
                style="width: 80px"
              />
            </template>
          </v-list-item>
        </v-list>

        <!-- Availability Impact Chart Preview -->
        <v-divider class="my-4" />
        <div class="text-subtitle-2 mb-2">Availability Impact by Category</div>
        <div v-for="item in downtimeRanking.slice(0, 5)" :key="item.category" class="mb-2">
          <div class="d-flex justify-space-between text-caption mb-1">
            <span>{{ item.category }}</span>
            <span class="text-error">-{{ item.oeeImpact }}%</span>
          </div>
          <v-progress-linear
            :model-value="(item.oeeImpact / totalOeeImpact) * 100"
            :color="getSeverityColor(item.severity)"
            height="8"
            rounded
          />
        </div>
      </template>
    </v-card-text>

    <v-card-actions v-if="downtimeRanking.length">
      <v-btn
        variant="text"
        color="warning"
        size="small"
        prepend-icon="mdi-chart-bar"
        @click="$emit('viewDetails')"
      >
        View Full Analysis
      </v-btn>
      <v-spacer />
      <v-chip size="x-small" variant="outlined" color="grey">
        Last updated: {{ lastUpdated }}
      </v-chip>
    </v-card-actions>
  </v-card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import axios from 'axios'

// Props
const props = defineProps<{
  clientId?: string
  dateRange?: string
  startDate?: string
  endDate?: string
}>()

// Emits
defineEmits(['viewDetails'])

// State
const loading = ref(false)
const error = ref<string | null>(null)
const downtimeRanking = ref<DowntimeImpactItem[]>([])
const lastUpdated = ref('')

// Types
interface DowntimeImpactItem {
  rank: number
  category: string
  totalHours: number
  oeeImpact: number
  eventCount: number
  severity: 'critical' | 'high' | 'medium' | 'low'
}

// Computed
const maxHours = computed(() => {
  if (!downtimeRanking.value.length) return 1
  return Math.max(...downtimeRanking.value.map(item => item.totalHours))
})

const totalDowntimeHours = computed(() => {
  return downtimeRanking.value.reduce((sum, item) => sum + item.totalHours, 0).toFixed(1)
})

const totalOeeImpact = computed(() => {
  return downtimeRanking.value.reduce((sum, item) => sum + item.oeeImpact, 0).toFixed(1)
})

// Methods
const getSeverityColor = (severity: string): string => {
  const colors: Record<string, string> = {
    critical: 'error',
    high: 'warning',
    medium: 'orange',
    low: 'grey'
  }
  return colors[severity] || 'grey'
}

const getImpactTextColor = (impact: number): string => {
  if (impact >= 5) return 'text-error'
  if (impact >= 2) return 'text-warning'
  return 'text-grey'
}

const determineSeverity = (oeeImpact: number): 'critical' | 'high' | 'medium' | 'low' => {
  if (oeeImpact >= 10) return 'critical'
  if (oeeImpact >= 5) return 'high'
  if (oeeImpact >= 2) return 'medium'
  return 'low'
}

const fetchData = async () => {
  loading.value = true
  error.value = null

  try {
    // Fetch downtime data from API
    const response = await axios.get('http://localhost:8000/api/v1/kpi/downtime-impact', {
      params: {
        client_id: props.clientId,
        start_date: props.startDate,
        end_date: props.endDate
      }
    })

    // Transform API response
    if (response.data && response.data.categories) {
      downtimeRanking.value = response.data.categories.map((cat: any, index: number) => ({
        rank: index + 1,
        category: cat.category || cat.downtime_category,
        totalHours: parseFloat(cat.total_hours || cat.duration_hours || 0),
        oeeImpact: parseFloat(cat.oee_impact || cat.availability_impact || 0),
        eventCount: cat.event_count || cat.count || 0,
        severity: determineSeverity(parseFloat(cat.oee_impact || cat.availability_impact || 0))
      }))
    } else {
      // Fallback: fetch from downtime events and calculate
      await fetchDowntimeEvents()
    }

    lastUpdated.value = new Date().toLocaleTimeString()
  } catch (err: any) {
    console.warn('Downtime impact API not available, using fallback calculation')
    await fetchDowntimeEvents()
  } finally {
    loading.value = false
  }
}

const fetchDowntimeEvents = async () => {
  try {
    // Fallback: aggregate from downtime events
    const response = await axios.get('http://localhost:8000/api/v1/downtime', {
      params: {
        start_date: props.startDate,
        end_date: props.endDate,
        limit: 1000
      }
    })

    if (response.data && Array.isArray(response.data)) {
      // Aggregate by category
      const categoryMap = new Map<string, { hours: number; count: number }>()

      response.data.forEach((event: any) => {
        const category = event.downtime_category || event.reason_category || 'Unknown'
        const hours = parseFloat(event.duration_hours || 0)

        if (categoryMap.has(category)) {
          const existing = categoryMap.get(category)!
          existing.hours += hours
          existing.count += 1
        } else {
          categoryMap.set(category, { hours, count: 1 })
        }
      })

      // Calculate total scheduled hours (assume 8h/shift, estimate from data)
      const totalScheduledHours = 480 // Default: 30 days * 16h/day

      // Sort by hours and create ranking
      const sorted = Array.from(categoryMap.entries())
        .sort((a, b) => b[1].hours - a[1].hours)
        .slice(0, 10)

      downtimeRanking.value = sorted.map(([category, data], index) => {
        const oeeImpact = (data.hours / totalScheduledHours) * 100
        return {
          rank: index + 1,
          category,
          totalHours: parseFloat(data.hours.toFixed(1)),
          oeeImpact: parseFloat(oeeImpact.toFixed(1)),
          eventCount: data.count,
          severity: determineSeverity(oeeImpact)
        }
      })
    }

    lastUpdated.value = new Date().toLocaleTimeString()
  } catch (err: any) {
    error.value = err.response?.data?.detail || 'Failed to load downtime data'
  }
}

// Lifecycle
onMounted(() => {
  fetchData()
})

// Watch for prop changes
watch(
  () => [props.clientId, props.dateRange, props.startDate, props.endDate],
  () => {
    fetchData()
  }
)
</script>

<style scoped>
.v-list-item {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 8px;
}
</style>
