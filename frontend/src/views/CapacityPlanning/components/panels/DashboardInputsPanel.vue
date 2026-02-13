<template>
  <v-card>
    <v-card-title class="d-flex align-center">
      <v-icon start>mdi-tune</v-icon>
      Dashboard Inputs
      <v-spacer />
      <v-chip
        v-if="isDirty"
        color="warning"
        size="small"
        variant="tonal"
        prepend-icon="mdi-circle-medium"
      >
        Unsaved changes
      </v-chip>
    </v-card-title>
    <v-card-text>
      <v-row>
        <!-- Planning Horizon -->
        <v-col cols="12" md="6">
          <v-text-field
            :model-value="inputs.planning_horizon_days"
            label="Planning Horizon (days)"
            type="number"
            :min="1"
            :max="365"
            variant="outlined"
            density="comfortable"
            hint="Number of days to plan ahead"
            persistent-hint
            prepend-inner-icon="mdi-calendar-range"
            @update:modelValue="update('planning_horizon_days', Number($event))"
          />
        </v-col>

        <!-- Shortage Alert Days -->
        <v-col cols="12" md="6">
          <v-text-field
            :model-value="inputs.shortage_alert_days"
            label="Stock Staleness Alert (days)"
            type="number"
            :min="1"
            :max="30"
            variant="outlined"
            density="comfortable"
            hint="Warn when stock snapshots older than this"
            persistent-hint
            prepend-inner-icon="mdi-alert-clock-outline"
            @update:modelValue="update('shortage_alert_days', Number($event))"
          />
        </v-col>

        <!-- Default Efficiency Slider -->
        <v-col cols="12" md="6">
          <div class="text-subtitle-2 mb-1">Default Efficiency (%)</div>
          <v-slider
            :model-value="inputs.default_efficiency"
            :min="50"
            :max="100"
            :step="1"
            thumb-label
            color="primary"
            track-color="grey-lighten-3"
            hide-details
            @update:modelValue="update('default_efficiency', Number($event))"
          >
            <template v-slot:append>
              <v-text-field
                :model-value="inputs.default_efficiency"
                type="number"
                :min="50"
                :max="100"
                density="compact"
                variant="outlined"
                style="width: 80px"
                hide-details
                @update:modelValue="update('default_efficiency', clampValue(Number($event), 50, 100))"
              />
            </template>
          </v-slider>
        </v-col>

        <!-- Bottleneck Threshold Slider -->
        <v-col cols="12" md="6">
          <div class="text-subtitle-2 mb-1">Bottleneck Threshold (%)</div>
          <v-slider
            :model-value="inputs.bottleneck_threshold"
            :min="50"
            :max="100"
            :step="1"
            thumb-label
            color="warning"
            track-color="grey-lighten-3"
            hide-details
            @update:modelValue="update('bottleneck_threshold', Number($event))"
          >
            <template v-slot:append>
              <v-text-field
                :model-value="inputs.bottleneck_threshold"
                type="number"
                :min="50"
                :max="100"
                density="compact"
                variant="outlined"
                style="width: 80px"
                hide-details
                @update:modelValue="update('bottleneck_threshold', clampValue(Number($event), 50, 100))"
              />
            </template>
          </v-slider>
          <div class="text-caption text-grey mt-1">
            Lines above this utilization are flagged
          </div>
        </v-col>

        <!-- Auto-Schedule Switch -->
        <v-col cols="12">
          <v-switch
            :model-value="inputs.auto_schedule_enabled"
            label="Auto-Schedule"
            color="primary"
            hint="Automatically generate schedules when orders change"
            persistent-hint
            @update:modelValue="update('auto_schedule_enabled', $event)"
          />
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { computed } from 'vue'
import { useCapacityPlanningStore } from '@/stores/capacityPlanningStore'

const store = useCapacityPlanningStore()

const inputs = computed(() => store.worksheets.dashboardInputs.data)
const isDirty = computed(() => store.worksheets.dashboardInputs.dirty)

const update = (key, value) => {
  store.updateDashboardInput(key, value)
}

const clampValue = (value, min, max) => {
  if (isNaN(value)) return min
  return Math.min(max, Math.max(min, value))
}
</script>
