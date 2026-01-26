<template>
  <div v-if="isEstimated" class="inference-indicator">
    <!-- ESTIMATED Badge -->
    <v-tooltip location="bottom" max-width="400">
      <template v-slot:activator="{ props }">
        <v-chip
          v-bind="props"
          size="x-small"
          :color="confidenceColor"
          variant="flat"
          class="ml-1 estimated-badge"
          :class="{ 'pulse-animation': highlightNew }"
        >
          <v-icon start size="12">mdi-information-outline</v-icon>
          {{ $t('kpi.estimated') }}
        </v-chip>
      </template>

      <!-- Tooltip content with inference breakdown -->
      <div class="inference-tooltip">
        <div class="tooltip-header">
          <v-icon size="16" class="mr-1">mdi-information</v-icon>
          {{ $t('kpi.estimated') }} {{ $t('kpi.confidence') }}: {{ formattedConfidence }}
        </div>

        <v-divider class="my-2" />

        <div class="tooltip-section">
          <div class="section-title">{{ $t('inferenceIndicator.dataSourcesTitle') }}</div>

          <div v-for="(detail, key) in inferenceDetails" :key="key" class="inference-item">
            <v-icon
              size="14"
              :color="detail.is_inferred ? 'warning' : 'success'"
              class="mr-1"
            >
              {{ detail.is_inferred ? 'mdi-alert-circle' : 'mdi-check-circle' }}
            </v-icon>
            <span class="item-label">{{ getFieldLabel(key) }}:</span>
            <span class="item-source">{{ formatSource(detail.source) }}</span>
            <v-chip
              v-if="detail.confidence"
              size="x-small"
              :color="getConfidenceChipColor(detail.confidence)"
              variant="tonal"
              class="ml-1"
            >
              {{ Math.round(detail.confidence * 100) }}%
            </v-chip>
          </div>
        </div>

        <v-divider class="my-2" />

        <div class="tooltip-footer">
          <v-icon size="14" class="mr-1">mdi-lightbulb-outline</v-icon>
          <span class="hint-text">{{ $t('inferenceIndicator.hintText') }}</span>
        </div>
      </div>
    </v-tooltip>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps({
  /**
   * Whether the KPI value is estimated/inferred
   */
  isEstimated: {
    type: Boolean,
    default: false
  },
  /**
   * Confidence score between 0 and 1
   */
  confidenceScore: {
    type: Number,
    default: 1.0,
    validator: (value) => value >= 0 && value <= 1
  },
  /**
   * Detailed inference breakdown object
   * Expected format: {
   *   cycle_time: { is_inferred: bool, source: string, confidence: number },
   *   employees: { is_inferred: bool, source: string, confidence: number },
   *   scheduled_hours: { is_inferred: bool, source: string }
   * }
   */
  inferenceDetails: {
    type: Object,
    default: () => ({})
  },
  /**
   * Highlight with animation (for newly updated values)
   */
  highlightNew: {
    type: Boolean,
    default: false
  }
})

// Computed
const formattedConfidence = computed(() => {
  return `${Math.round(props.confidenceScore * 100)}%`
})

const confidenceColor = computed(() => {
  if (props.confidenceScore >= 0.8) return 'success'
  if (props.confidenceScore >= 0.5) return 'warning'
  return 'error'
})

// Methods
const getConfidenceChipColor = (confidence) => {
  if (confidence >= 0.8) return 'success'
  if (confidence >= 0.5) return 'warning'
  return 'error'
}

const getFieldLabel = (key) => {
  const labels = {
    cycle_time: t('inferenceIndicator.fields.cycleTime'),
    employees: t('inferenceIndicator.fields.employees'),
    scheduled_hours: t('inferenceIndicator.fields.scheduledHours'),
    opportunities: t('inferenceIndicator.fields.opportunities'),
    threshold: t('inferenceIndicator.fields.threshold')
  }
  return labels[key] || key
}

const formatSource = (source) => {
  if (!source) return t('inferenceIndicator.sources.unknown')

  const sourceMap = {
    'product_standard': t('inferenceIndicator.sources.productStandard'),
    'historical_avg': t('inferenceIndicator.sources.historicalAverage'),
    'historical_shift_avg': t('inferenceIndicator.sources.historicalShiftAverage'),
    'client_default': t('inferenceIndicator.sources.clientDefault'),
    'global_default': t('inferenceIndicator.sources.globalDefault'),
    'default': t('inferenceIndicator.sources.systemDefault'),
    'employees_assigned': t('inferenceIndicator.sources.employeesAssigned'),
    'employees_present': t('inferenceIndicator.sources.employeesPresent'),
    'shift_times': t('inferenceIndicator.sources.shiftTimes')
  }

  // Handle floating pool additions
  if (source.includes('+floating_pool')) {
    const base = source.split('+')[0]
    const fpMatch = source.match(/floating_pool\((\d+)\)/)
    const fpCount = fpMatch ? fpMatch[1] : '?'
    return `${sourceMap[base] || base} + ${fpCount} ${t('inferenceIndicator.sources.floatingPool')}`
  }

  return sourceMap[source] || source
}
</script>

<style scoped>
.inference-indicator {
  display: inline-flex;
  align-items: center;
}

.estimated-badge {
  font-size: 10px;
  height: 18px !important;
  cursor: help;
}

.pulse-animation {
  animation: pulse 2s ease-in-out 3;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.6;
  }
}

.inference-tooltip {
  padding: 4px;
}

.tooltip-header {
  font-weight: 600;
  display: flex;
  align-items: center;
  color: #90caf9;
}

.tooltip-section {
  margin: 8px 0;
}

.section-title {
  font-weight: 500;
  margin-bottom: 6px;
  color: #e0e0e0;
}

.inference-item {
  display: flex;
  align-items: center;
  margin: 4px 0;
  font-size: 12px;
}

.item-label {
  color: #bdbdbd;
  margin-right: 4px;
}

.item-source {
  color: #ffffff;
}

.tooltip-footer {
  display: flex;
  align-items: flex-start;
  font-size: 11px;
  color: #9e9e9e;
}

.hint-text {
  line-height: 1.3;
}
</style>
