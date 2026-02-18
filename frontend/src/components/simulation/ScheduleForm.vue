<template>
  <v-card>
    <v-card-title class="bg-info">
      <div class="d-flex align-center">
        <v-icon class="mr-2">mdi-clock-outline</v-icon>
        <span class="text-h6">Schedule Configuration</span>
      </div>
    </v-card-title>

    <v-card-text>
      <v-row>
        <!-- Shifts Configuration -->
        <v-col cols="12" md="6">
          <v-card variant="outlined">
            <v-card-title class="text-subtitle-1">
              <v-icon left size="small">mdi-account-group</v-icon>
              Shifts
            </v-card-title>
            <v-card-text>
              <v-slider
                v-model="store.schedule.shifts_enabled"
                :min="1"
                :max="3"
                :step="1"
                :ticks="{ 1: '1 Shift', 2: '2 Shifts', 3: '3 Shifts' }"
                show-ticks="always"
                tick-size="4"
                thumb-label
                class="mb-4"
              />

              <v-row dense>
                <v-col cols="12">
                  <v-text-field
                    v-model.number="store.schedule.shift1_hours"
                    :label="t('simulationV2.schedule.shift1Hours')"
                    type="number"
                    :min="1"
                    :max="12"
                    step="0.5"
                    variant="outlined"
                    density="compact"
                    suffix="hours"
                  />
                </v-col>
                <v-col cols="12" v-if="store.schedule.shifts_enabled >= 2">
                  <v-text-field
                    v-model.number="store.schedule.shift2_hours"
                    :label="t('simulationV2.schedule.shift2Hours')"
                    type="number"
                    :min="0"
                    :max="12"
                    step="0.5"
                    variant="outlined"
                    density="compact"
                    suffix="hours"
                  />
                </v-col>
                <v-col cols="12" v-if="store.schedule.shifts_enabled >= 3">
                  <v-text-field
                    v-model.number="store.schedule.shift3_hours"
                    :label="t('simulationV2.schedule.shift3Hours')"
                    type="number"
                    :min="0"
                    :max="12"
                    step="0.5"
                    variant="outlined"
                    density="compact"
                    suffix="hours"
                  />
                </v-col>
              </v-row>
            </v-card-text>
          </v-card>
        </v-col>

        <!-- Work Days & Overtime -->
        <v-col cols="12" md="6">
          <v-card variant="outlined">
            <v-card-title class="text-subtitle-1">
              <v-icon left size="small">mdi-calendar-week</v-icon>
              Work Days & Overtime
            </v-card-title>
            <v-card-text>
              <v-slider
                v-model="store.schedule.work_days"
                :min="1"
                :max="7"
                :step="1"
                :ticks="{ 5: '5 days', 6: '6 days', 7: '7 days' }"
                show-ticks="always"
                tick-size="4"
                thumb-label
                class="mb-4"
              />

              <v-switch
                v-model="store.schedule.ot_enabled"
                :label="t('simulationV2.schedule.enableOvertime')"
                color="primary"
                density="compact"
                hide-details
                class="mb-3"
              />

              <div v-if="store.schedule.ot_enabled">
                <v-row dense>
                  <v-col cols="12">
                    <v-text-field
                      v-model.number="store.schedule.weekday_ot_hours"
                      :label="t('simulationV2.schedule.weekdayOtHours')"
                      type="number"
                      :min="0"
                      :max="8"
                      step="0.5"
                      variant="outlined"
                      density="compact"
                      suffix="hours"
                    />
                  </v-col>
                  <v-col cols="6">
                    <v-text-field
                      v-model.number="store.schedule.weekend_ot_days"
                      :label="t('simulationV2.schedule.weekendOtDays')"
                      type="number"
                      :min="0"
                      :max="2"
                      variant="outlined"
                      density="compact"
                      suffix="days"
                    />
                  </v-col>
                  <v-col cols="6">
                    <v-text-field
                      v-model.number="store.schedule.weekend_ot_hours"
                      :label="t('simulationV2.schedule.weekendOtHours')"
                      type="number"
                      :min="0"
                      :max="12"
                      step="0.5"
                      variant="outlined"
                      density="compact"
                      suffix="hours"
                    />
                  </v-col>
                </v-row>
              </div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <!-- Summary -->
      <v-card variant="tonal" color="primary" class="mt-4">
        <v-card-text>
          <v-row align="center">
            <v-col cols="6" md="3">
              <div class="text-caption text-medium-emphasis">Daily Planned Hours</div>
              <div class="text-h5">{{ store.dailyPlannedHours.toFixed(1) }}h</div>
            </v-col>
            <v-col cols="6" md="3">
              <div class="text-caption text-medium-emphasis">Weekly Base Hours</div>
              <div class="text-h5">{{ weeklyBaseHours.toFixed(1) }}h</div>
            </v-col>
            <v-col cols="6" md="3">
              <div class="text-caption text-medium-emphasis">Weekly with OT</div>
              <div class="text-h5">{{ weeklyTotalHours.toFixed(1) }}h</div>
            </v-col>
            <v-col cols="6" md="3">
              <div class="text-caption text-medium-emphasis">Total Shift Hours</div>
              <div class="text-h5">{{ totalShiftHours.toFixed(1) }}h</div>
            </v-col>
          </v-row>
        </v-card-text>
      </v-card>

      <v-alert
        v-if="totalShiftHours > 24"
        type="error"
        variant="tonal"
        density="compact"
        class="mt-3"
      >
        Total shift hours ({{ totalShiftHours.toFixed(1) }}h) exceed 24 hours per day.
      </v-alert>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSimulationV2Store } from '@/stores/simulationV2Store'

const { t } = useI18n()
const store = useSimulationV2Store()

const totalShiftHours = computed(() => {
  return (Number(store.schedule.shift1_hours) || 0) +
         (Number(store.schedule.shift2_hours) || 0) +
         (Number(store.schedule.shift3_hours) || 0)
})

const weeklyBaseHours = computed(() => {
  return (Number(store.dailyPlannedHours) || 0) * (Number(store.schedule.work_days) || 0)
})

const weeklyTotalHours = computed(() => {
  let total = weeklyBaseHours.value
  if (store.schedule.ot_enabled) {
    total += (Number(store.schedule.weekday_ot_hours) || 0) * (Number(store.schedule.work_days) || 0)
    total += (Number(store.schedule.weekend_ot_hours) || 0) * (Number(store.schedule.weekend_ot_days) || 0)
  }
  return total
})
</script>
