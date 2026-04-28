<template>
  <v-card>
    <v-card-title class="d-flex align-center">
      <v-icon start>mdi-book-open-variant</v-icon>
      {{ t('capacityInstructions.title') }}
    </v-card-title>
    <v-card-text>
      <v-expansion-panels multiple>
        <!-- Section 1: Calculation Guide -->
        <v-expansion-panel>
          <v-expansion-panel-title>
            <v-icon start>mdi-calculator-variant</v-icon>
            {{ t('capacityInstructions.calculationGuide') }}
          </v-expansion-panel-title>
          <v-expansion-panel-text>
            <v-list density="compact">
              <v-list-item
                v-for="step in calculationSteps"
                :key="step.number"
              >
                <template v-slot:prepend>
                  <v-avatar size="28" color="primary" variant="tonal" class="mr-2">
                    <span class="text-caption font-weight-bold">{{ step.number }}</span>
                  </v-avatar>
                </template>
                <v-list-item-title class="font-weight-medium">
                  {{ step.title }}
                </v-list-item-title>
                <v-list-item-subtitle>
                  {{ step.description }}
                </v-list-item-subtitle>
              </v-list-item>
            </v-list>
          </v-expansion-panel-text>
        </v-expansion-panel>

        <!-- Section 2: Common Pitfalls -->
        <v-expansion-panel>
          <v-expansion-panel-title>
            <v-icon start>mdi-alert-circle-outline</v-icon>
            {{ t('capacityInstructions.commonPitfalls') }}
          </v-expansion-panel-title>
          <v-expansion-panel-text>
            <v-alert
              v-for="(pitfall, index) in commonPitfalls"
              :key="index"
              type="warning"
              variant="tonal"
              density="compact"
              class="mb-2"
            >
              {{ pitfall }}
            </v-alert>
          </v-expansion-panel-text>
        </v-expansion-panel>

        <!-- Section 3: Key Formulas -->
        <v-expansion-panel>
          <v-expansion-panel-title>
            <v-icon start>mdi-function-variant</v-icon>
            {{ t('capacityInstructions.keyFormulas') }}
          </v-expansion-panel-title>
          <v-expansion-panel-text>
            <v-card
              v-for="(formula, index) in keyFormulas"
              :key="index"
              variant="outlined"
              class="mb-2"
            >
              <v-card-text class="py-2 px-3">
                <div class="text-subtitle-2 text-medium-emphasis">{{ formula.label }}</div>
                <div class="text-body-1 font-weight-medium font-italic mt-1">
                  {{ formula.expression }}
                </div>
              </v-card-text>
            </v-card>
          </v-expansion-panel-text>
        </v-expansion-panel>
      </v-expansion-panels>
    </v-card-text>
  </v-card>
</template>

<script setup>
/**
 * InstructionsPanel - Reference guide for capacity planning methodology.
 *
 * Static read-only panel with three expandable sections: the 12-step capacity
 * calculation procedure, common pitfalls to avoid, and key formulas
 * (net capacity, utilization, SAM per order, gross required, coverage).
 * Purely informational -- no store dependency, props, or emits.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

// Wrapped in computed() so the titles/descriptions re-resolve on
// locale switch — were previously a mix of hardcoded English text
// and t() calls only on step 10. All keys already exist under
// capacityInstructions.steps.* / .pitfalls.* / .formulas.*
const calculationSteps = computed(() => [
  { number: 1, title: t('capacityInstructions.steps.workingDays'), description: t('capacityInstructions.steps.workingDaysDesc') },
  { number: 2, title: t('capacityInstructions.steps.shiftsPerDay'), description: t('capacityInstructions.steps.shiftsPerDayDesc') },
  { number: 3, title: t('capacityInstructions.steps.hoursPerShift'), description: t('capacityInstructions.steps.hoursPerShiftDesc') },
  { number: 4, title: t('capacityInstructions.steps.grossHours'), description: t('capacityInstructions.steps.grossHoursDesc') },
  { number: 5, title: t('capacityInstructions.steps.efficiency'), description: t('capacityInstructions.steps.efficiencyDesc') },
  { number: 6, title: t('capacityInstructions.steps.absenteeism'), description: t('capacityInstructions.steps.absenteeismDesc') },
  { number: 7, title: t('capacityInstructions.steps.netHours'), description: t('capacityInstructions.steps.netHoursDesc') },
  { number: 8, title: t('capacityInstructions.steps.operators'), description: t('capacityInstructions.steps.operatorsDesc') },
  { number: 9, title: t('capacityInstructions.steps.totalCapacity'), description: t('capacityInstructions.steps.totalCapacityDesc') },
  { number: 10, title: t('capacityInstructions.steps.demandHours'), description: t('capacityInstructions.steps.demandHoursDesc') },
  { number: 11, title: t('capacityInstructions.steps.utilization'), description: t('capacityInstructions.steps.utilizationDesc') },
  { number: 12, title: t('capacityInstructions.steps.bottleneck'), description: t('capacityInstructions.steps.bottleneckDesc') }
])

const commonPitfalls = computed(() => [
  t('capacityInstructions.pitfalls.holidays'),
  t('capacityInstructions.pitfalls.grossHours'),
  t('capacityInstructions.pitfalls.setupTime'),
  t('capacityInstructions.pitfalls.learningCurve'),
  t('capacityInstructions.pitfalls.doubleCount'),
  t('capacityInstructions.pitfalls.stockSnapshots'),
  t('capacityInstructions.pitfalls.dateRanges')
])

const keyFormulas = computed(() => [
  {
    label: t('capacityInstructions.formulas.netCapacity'),
    expression: t('capacityInstructions.formulas.netCapacityExpr')
  },
  {
    label: t('capacityInstructions.formulas.utilization'),
    expression: t('capacityInstructions.formulas.utilizationExpr')
  },
  {
    label: t('timeStandard.samPerOrder'),
    expression: t('timeStandard.samExpression')
  },
  {
    label: t('capacityInstructions.formulas.grossRequired'),
    expression: t('capacityInstructions.formulas.grossRequiredExpr')
  },
  {
    label: t('capacityInstructions.formulas.coverage'),
    expression: t('capacityInstructions.formulas.coverageExpr')
  }
])
</script>
