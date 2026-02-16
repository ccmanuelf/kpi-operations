<template>
  <v-card>
    <v-card-title class="d-flex align-center">
      <v-icon start>mdi-book-open-variant</v-icon>
      Capacity Planning Reference Guide
    </v-card-title>
    <v-card-text>
      <v-expansion-panels multiple>
        <!-- Section 1: Calculation Guide -->
        <v-expansion-panel>
          <v-expansion-panel-title>
            <v-icon start>mdi-calculator-variant</v-icon>
            12-Step Capacity Calculation
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
            Common Pitfalls
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
            Key Formulas
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
const calculationSteps = [
  { number: 1, title: 'Working Days', description: 'Count calendar working days in period' },
  { number: 2, title: 'Shifts per Day', description: 'Multiply by available shifts' },
  { number: 3, title: 'Hours per Shift', description: 'Standard hours (typically 8h)' },
  { number: 4, title: 'Gross Available Hours', description: 'Days \u00d7 Shifts \u00d7 Hours' },
  { number: 5, title: 'Efficiency Factor', description: 'Apply line efficiency (typically 85%)' },
  { number: 6, title: 'Absenteeism Factor', description: 'Deduct absenteeism (typically 5%)' },
  { number: 7, title: 'Net Available Hours', description: 'Gross \u00d7 Efficiency \u00d7 (1 \u2212 Absenteeism)' },
  { number: 8, title: 'Operators per Line', description: 'Multiply by available operators' },
  { number: 9, title: 'Total Capacity Hours', description: 'Net Hours \u00d7 Operators' },
  { number: 10, title: 'Demand Hours', description: 'Sum SAM \u00d7 Quantity for all orders' },
  { number: 11, title: 'Utilization %', description: '(Demand / Capacity) \u00d7 100' },
  { number: 12, title: 'Bottleneck Detection', description: 'Flag lines above threshold' }
]

const commonPitfalls = [
  'Forgetting to exclude holidays from working days',
  'Using gross hours instead of net hours for capacity',
  'Not accounting for setup time between style changes',
  'Ignoring learning curve for new styles (first 3 days typically 70% efficiency)',
  'Double-counting operators shared between lines',
  'Not updating stock snapshots before running MRP',
  'Comparing scenarios with different date ranges'
]

const keyFormulas = [
  {
    label: 'Net Capacity',
    expression: 'Working Days \u00d7 Shifts \u00d7 Hours \u00d7 Efficiency \u00d7 (1 \u2212 Absenteeism) \u00d7 Operators'
  },
  {
    label: 'Utilization %',
    expression: '(Total Demand Hours / Total Capacity Hours) \u00d7 100'
  },
  {
    label: 'SAM per Order',
    expression: 'Sum of Operation SAMs \u00d7 Order Quantity'
  },
  {
    label: 'Gross Required',
    expression: 'Quantity Per \u00d7 Order Qty \u00d7 (1 + Waste%)'
  },
  {
    label: 'Coverage %',
    expression: '(Available Qty / Required Qty) \u00d7 100'
  }
]
</script>
