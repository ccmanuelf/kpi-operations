<template>
  <v-dialog
    :model-value="modelValue"
    max-width="800"
    scrollable
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <v-card>
      <v-card-title class="d-flex align-center bg-primary text-white">
        <v-icon start>mdi-check-decagram</v-icon>
        MRP / Component Check Results
        <v-spacer />
        <v-btn
          icon="mdi-close"
          variant="text"
          size="small"
          @click="$emit('close')"
        />
      </v-card-title>
      <v-card-text v-if="results" class="pa-4">
        <!-- Summary -->
        <v-row class="mb-4">
          <v-col cols="4">
            <v-card variant="tonal" color="primary">
              <v-card-text class="text-center">
                <div class="text-h4">{{ results.total_components || 0 }}</div>
                <div class="text-subtitle-1">Total Components</div>
              </v-card-text>
            </v-card>
          </v-col>
          <v-col cols="4">
            <v-card variant="tonal" color="success">
              <v-card-text class="text-center">
                <div class="text-h4">{{ results.available_count || 0 }}</div>
                <div class="text-subtitle-1">Available</div>
              </v-card-text>
            </v-card>
          </v-col>
          <v-col cols="4">
            <v-card variant="tonal" color="error">
              <v-card-text class="text-center">
                <div class="text-h4">{{ results.shortage_count || 0 }}</div>
                <div class="text-subtitle-1">Shortages</div>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>

        <!-- Shortages Alert -->
        <v-alert
          v-if="results.shortage_count > 0"
          type="warning"
          variant="tonal"
          class="mb-4"
        >
          <strong>{{ results.shortage_count }} component shortages detected.</strong>
          Review the shortages below and take action to resolve them before production.
        </v-alert>

        <!-- Component Details -->
        <v-expansion-panels v-if="results.components?.length">
          <v-expansion-panel title="Shortages" v-if="shortages.length">
            <v-expansion-panel-text>
              <v-list density="compact">
                <v-list-item
                  v-for="(item, index) in shortages"
                  :key="index"
                  class="px-0"
                >
                  <template v-slot:prepend>
                    <v-icon color="error">mdi-alert-circle</v-icon>
                  </template>
                  <v-list-item-title>{{ item.component_item_code }}</v-list-item-title>
                  <v-list-item-subtitle>
                    {{ item.component_description }}
                    <br />
                    Required: {{ item.required_quantity }} | Available: {{ item.available_quantity }} |
                    <strong class="text-error">Short: {{ item.shortage_quantity }}</strong>
                  </v-list-item-subtitle>
                </v-list-item>
              </v-list>
            </v-expansion-panel-text>
          </v-expansion-panel>

          <v-expansion-panel title="Partial Availability" v-if="partials.length">
            <v-expansion-panel-text>
              <v-list density="compact">
                <v-list-item
                  v-for="(item, index) in partials"
                  :key="index"
                  class="px-0"
                >
                  <template v-slot:prepend>
                    <v-icon color="warning">mdi-alert</v-icon>
                  </template>
                  <v-list-item-title>{{ item.component_item_code }}</v-list-item-title>
                  <v-list-item-subtitle>
                    {{ item.component_description }}
                    <br />
                    Required: {{ item.required_quantity }} | Available: {{ item.available_quantity }}
                  </v-list-item-subtitle>
                </v-list-item>
              </v-list>
            </v-expansion-panel-text>
          </v-expansion-panel>

          <v-expansion-panel title="Available Components">
            <v-expansion-panel-text>
              <v-list density="compact">
                <v-list-item
                  v-for="(item, index) in availables"
                  :key="index"
                  class="px-0"
                >
                  <template v-slot:prepend>
                    <v-icon color="success">mdi-check-circle</v-icon>
                  </template>
                  <v-list-item-title>{{ item.component_item_code }}</v-list-item-title>
                  <v-list-item-subtitle>
                    {{ item.component_description }}
                    <br />
                    Required: {{ item.required_quantity }} | Available: {{ item.available_quantity }}
                  </v-list-item-subtitle>
                </v-list-item>
              </v-list>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>

        <!-- No Results -->
        <div v-else class="text-center pa-4 text-grey">
          No component data available.
        </div>
      </v-card-text>
      <v-card-text v-else class="text-center pa-8 text-grey">
        No MRP results available.
      </v-card-text>
      <v-card-actions>
        <v-btn variant="tonal" @click="exportResults">
          <v-icon start>mdi-download</v-icon>
          Export Results
        </v-btn>
        <v-spacer />
        <v-btn color="primary" @click="$emit('close')">Close</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  results: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['update:modelValue', 'close'])

const shortages = computed(() =>
  props.results?.components?.filter(c => c.status === 'SHORTAGE') || []
)

const partials = computed(() =>
  props.results?.components?.filter(c => c.status === 'PARTIAL') || []
)

const availables = computed(() =>
  props.results?.components?.filter(c => c.status === 'AVAILABLE') || []
)

const exportResults = () => {
  if (!props.results) return

  const json = JSON.stringify(props.results, null, 2)
  const blob = new Blob([json], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `mrp-results-${new Date().toISOString().slice(0, 10)}.json`
  link.click()
  URL.revokeObjectURL(url)
}
</script>
