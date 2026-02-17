<template>
  <v-card :variant="variant" :class="blockClass">
    <!-- Header -->
    <v-card-title class="d-flex align-center" :class="headerClass">
      <v-icon v-if="icon" :color="iconColor" class="mr-2">{{ icon }}</v-icon>
      <span :class="titleClass">{{ title }}</span>
      <v-spacer />
      <slot name="header-actions">
        <v-tooltip v-if="tooltip" location="top">
          <template v-slot:activator="{ props }">
            <v-icon v-bind="props" size="small" class="text-medium-emphasis">mdi-information-outline</v-icon>
          </template>
          {{ tooltip }}
        </v-tooltip>
      </slot>
    </v-card-title>

    <!-- Optional Subtitle -->
    <v-card-subtitle v-if="subtitle" class="pb-0">
      {{ subtitle }}
    </v-card-subtitle>

    <!-- Content -->
    <v-card-text :class="contentClass">
      <!-- Stats Layout -->
      <template v-if="layout === 'stats'">
        <v-row dense>
          <v-col
            v-for="(stat, idx) in stats"
            :key="idx"
            :cols="statCols"
            :md="statMd"
          >
            <div class="stat-item text-center pa-2">
              <div class="text-h5 font-weight-bold" :class="stat.color ? `text-${stat.color}` : ''">
                {{ formatValue(stat.value, stat.format) }}
              </div>
              <div class="text-caption text-medium-emphasis">{{ stat.label }}</div>
              <div v-if="stat.sublabel" class="text-caption text-disabled">{{ stat.sublabel }}</div>
            </div>
          </v-col>
        </v-row>
      </template>

      <!-- List Layout -->
      <template v-else-if="layout === 'list'">
        <v-list density="compact" class="bg-transparent">
          <v-list-item
            v-for="(item, idx) in items"
            :key="idx"
            :class="item.class"
          >
            <template v-slot:prepend v-if="item.icon">
              <v-icon :color="item.iconColor || 'primary'" size="small">{{ item.icon }}</v-icon>
            </template>
            <v-list-item-title>{{ item.title }}</v-list-item-title>
            <v-list-item-subtitle v-if="item.subtitle">{{ item.subtitle }}</v-list-item-subtitle>
            <template v-slot:append v-if="item.value !== undefined">
              <span class="font-weight-bold" :class="item.valueColor ? `text-${item.valueColor}` : ''">
                {{ formatValue(item.value, item.format) }}
              </span>
            </template>
          </v-list-item>
        </v-list>
      </template>

      <!-- Chips Layout -->
      <template v-else-if="layout === 'chips'">
        <div class="d-flex flex-wrap ga-2">
          <v-chip
            v-for="(chip, idx) in chips"
            :key="idx"
            :color="chip.color || 'primary'"
            :variant="chip.variant || 'tonal'"
            :size="chip.size || 'default'"
          >
            <v-icon v-if="chip.icon" start>{{ chip.icon }}</v-icon>
            {{ chip.label }}
          </v-chip>
        </div>
        <div v-if="chips?.length === 0" class="text-caption text-medium-emphasis">
          {{ emptyMessage || 'No items' }}
        </div>
      </template>

      <!-- Progress Layout -->
      <template v-else-if="layout === 'progress'">
        <div v-for="(bar, idx) in progressBars" :key="idx" class="mb-3">
          <div class="d-flex justify-space-between mb-1">
            <span class="text-caption">{{ bar.label }}</span>
            <span class="text-caption font-weight-bold">{{ bar.value }}%</span>
          </div>
          <v-progress-linear
            :model-value="bar.value"
            :color="bar.color || getProgressColor(bar.value)"
            height="8"
            rounded
          />
        </div>
      </template>

      <!-- Table Layout -->
      <template v-else-if="layout === 'table'">
        <v-table density="compact" class="results-table">
          <thead>
            <tr>
              <th v-for="col in columns" :key="col.key" :class="col.class">{{ col.label }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, idx) in tableData" :key="idx">
              <td v-for="col in columns" :key="col.key" :class="col.cellClass">
                {{ formatValue(row[col.key], col.format) }}
              </td>
            </tr>
          </tbody>
        </v-table>
      </template>

      <!-- Default Slot -->
      <template v-else>
        <slot />
      </template>
    </v-card-text>

    <!-- Optional Actions -->
    <v-card-actions v-if="$slots.actions" class="pt-0">
      <slot name="actions" />
    </v-card-actions>

    <!-- Loading Overlay -->
    <v-overlay
      v-model="loading"
      contained
      class="align-center justify-center"
      scrim="white"
    >
      <v-progress-circular indeterminate color="primary" />
    </v-overlay>
  </v-card>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  // Basic props
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
  icon: { type: String, default: '' },
  iconColor: { type: String, default: 'primary' },
  tooltip: { type: String, default: '' },

  // Layout type: 'stats', 'list', 'chips', 'progress', 'table', or 'custom' (use slot)
  layout: { type: String, default: 'custom' },

  // Card styling
  variant: { type: String, default: 'outlined' },
  elevation: { type: [Number, String], default: 0 },
  dense: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },

  // Stats layout
  stats: { type: Array, default: () => [] },
  statCols: { type: [Number, String], default: 6 },
  statMd: { type: [Number, String], default: 3 },

  // List layout
  items: { type: Array, default: () => [] },

  // Chips layout
  chips: { type: Array, default: () => [] },
  emptyMessage: { type: String, default: '' },

  // Progress layout
  progressBars: { type: Array, default: () => [] },

  // Table layout
  columns: { type: Array, default: () => [] },
  tableData: { type: Array, default: () => [] }
})

const blockClass = computed(() => ({
  'results-block': true,
  'results-block--dense': props.dense
}))

const headerClass = computed(() => ({
  'text-subtitle-1': props.dense,
  'py-2': props.dense
}))

const titleClass = computed(() => ({
  'text-subtitle-1': props.dense,
  'text-h6': !props.dense
}))

const contentClass = computed(() => ({
  'pt-0': props.dense
}))

/**
 * Format value based on type
 */
const formatValue = (value, format) => {
  if (value === null || value === undefined) return '-'

  switch (format) {
    case 'percent':
      return `${Number(value).toFixed(1)}%`
    case 'number':
      return Number(value).toLocaleString()
    case 'decimal':
      return Number(value).toFixed(2)
    case 'integer':
      return Math.round(Number(value)).toLocaleString()
    case 'time':
      return `${Number(value).toFixed(1)} min`
    case 'hours':
      return `${Number(value).toFixed(1)}h`
    default:
      return value
  }
}

/**
 * Get progress bar color based on value
 */
const getProgressColor = (value) => {
  if (value >= 95) return 'error'
  if (value >= 80) return 'warning'
  if (value <= 50) return 'info'
  return 'success'
}
</script>

<style scoped>
.results-block {
  height: 100%;
}

.results-block--dense .v-card-title {
  padding: 8px 16px;
}

.results-block--dense .v-card-text {
  padding: 8px 16px;
}

.stat-item {
  border-radius: 8px;
  background: rgba(var(--v-theme-surface-variant), 0.3);
}

.results-table th {
  white-space: nowrap;
}

.results-table td {
  white-space: nowrap;
}
</style>
