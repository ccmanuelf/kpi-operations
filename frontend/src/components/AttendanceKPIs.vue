<template>
  <div>
    <v-row class="mb-4">
      <v-col cols="12">
        <h2 class="text-h4 font-weight-bold">{{ t('attendanceKpis.phaseTitle') }}</h2>
        <p class="text-subtitle-1 text-grey">{{ t('attendanceKpis.kpiSubtitle') }}</p>
      </v-col>
    </v-row>

    <!-- KPI Card -->
    <v-row>
      <v-col cols="12" md="6">
        <v-card elevation="2">
          <v-card-title class="bg-error text-white">
            <v-icon left>mdi-account-alert</v-icon>
            {{ t('attendanceKpis.kpiTitle') }}
          </v-card-title>
          <v-card-text class="pa-6">
            <div class="text-h2 font-weight-bold text-error text-center">
              {{ absenteeism }}%
            </div>
            <v-progress-linear
              :model-value="absenteeism"
              color="error"
              height="20"
              class="mt-4"
            >
              <strong>{{ absenteeism }}%</strong>
            </v-progress-linear>
            <div class="mt-4">
              <div class="text-subtitle-2 text-grey">{{ t('attendanceKpis.formula') }}</div>
              <code class="text-caption">{{ t('attendanceKpis.formulaText') }}</code>
            </div>
            <div class="mt-4">
              <div class="text-subtitle-2 text-grey">{{ t('attendanceKpis.targetLabel') }}</div>
              <v-chip
                :color="absenteeism < 5 ? 'success' : absenteeism < 10 ? 'warning' : 'error'"
                size="small"
                class="mt-2"
              >
                {{ absenteeism < 5 ? t('attendanceKpis.excellent') : absenteeism < 10 ? t('attendanceKpis.good') : t('attendanceKpis.needsImprovement') }}
              </v-chip>
            </div>
            <div class="mt-2">
              <v-chip color="success" size="small">
                <v-icon left small>mdi-check</v-icon>
                Active
              </v-chip>
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="6">
        <v-card elevation="2">
          <v-card-title>{{ t('attendanceKpis.absenceBreakdown') }}</v-card-title>
          <v-card-text>
            <v-list>
              <v-list-item v-for="(item, index) in absenceBreakdown" :key="index">
                <template v-slot:prepend>
                  <v-icon :color="item.color">{{ item.icon }}</v-icon>
                </template>
                <v-list-item-title>{{ item.type }}</v-list-item-title>
                <template v-slot:append>
                  <v-chip size="small" :color="item.color">
                    {{ item.percentage }}%
                  </v-chip>
                </template>
              </v-list-item>
            </v-list>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Attendance Trend -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card elevation="2">
          <v-card-title>{{ t('attendanceKpis.attendanceTrend') }}</v-card-title>
          <v-card-text>
            <div class="text-center text-grey pa-8">
              {{ t('attendanceKpis.chartPlaceholder') }}
              <v-icon size="64" class="mt-4">mdi-chart-timeline-variant</v-icon>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Floating Pool Coverage -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card elevation="2">
          <v-card-title>{{ t('attendanceKpis.floatingPoolCoverage') }}</v-card-title>
          <v-card-text>
            <v-row>
              <v-col cols="4" class="text-center">
                <div class="text-h3 font-weight-bold text-primary">{{ floatingPool.total }}</div>
                <div class="text-caption text-grey">{{ t('attendanceKpis.totalFloatingStaff') }}</div>
              </v-col>
              <v-col cols="4" class="text-center">
                <div class="text-h3 font-weight-bold text-success">{{ floatingPool.active }}</div>
                <div class="text-caption text-grey">{{ t('attendanceKpis.currentlyCovering') }}</div>
              </v-col>
              <v-col cols="4" class="text-center">
                <div class="text-h3 font-weight-bold text-info">{{ floatingPool.available }}</div>
                <div class="text-caption text-grey">{{ t('common.available') }}</div>
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import axios from 'axios'

const { t } = useI18n()

const props = defineProps<{
  dateRange: string
}>()

const absenteeism = ref(0)
const absenceBreakdown = ref([
  { type: t('attendanceKpis.unscheduledAbsence'), percentage: 0, color: 'error', icon: 'mdi-alert-circle' },
  { type: t('attendanceKpis.vacation'), percentage: 0, color: 'info', icon: 'mdi-beach' },
  { type: t('attendanceKpis.medicalLeave'), percentage: 0, color: 'warning', icon: 'mdi-hospital-box' },
  { type: t('attendanceKpis.personalLeave'), percentage: 0, color: 'grey', icon: 'mdi-account' }
])
const floatingPool = ref({
  total: 0,
  active: 0,
  available: 0
})

const fetchData = async () => {
  try {
    const response = await axios.get('/api/attendance/kpi/absenteeism')
    absenteeism.value = parseFloat(response.data.absenteeism_rate.toFixed(1))

    // Mock absence breakdown (would come from API). Round numerically
    // — the template formats the value with `{{ item.percentage }}%`
    // so keeping `percentage` as a number matches the breakdown's
    // initial `percentage: 0` typing.
    absenceBreakdown.value[0].percentage = Math.round(absenteeism.value * 0.4 * 10) / 10
    absenceBreakdown.value[1].percentage = Math.round(absenteeism.value * 0.3 * 10) / 10
    absenceBreakdown.value[2].percentage = Math.round(absenteeism.value * 0.2 * 10) / 10
    absenceBreakdown.value[3].percentage = Math.round(absenteeism.value * 0.1 * 10) / 10

    // Mock floating pool data
    floatingPool.value = {
      total: 5,
      active: 3,
      available: 2
    }
  } catch (error) {
    console.error('Error fetching attendance KPIs:', error)
  }
}

onMounted(() => {
  fetchData()
})
</script>
