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
        {{ t('capacityPlanning.mrp.title') }}
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
                <div class="text-subtitle-1">{{ t('capacityPlanning.mrp.totalComponents') }}</div>
              </v-card-text>
            </v-card>
          </v-col>
          <v-col cols="4">
            <v-card variant="tonal" color="success">
              <v-card-text class="text-center">
                <div class="text-h4">{{ results.available_count || 0 }}</div>
                <div class="text-subtitle-1">{{ t('capacityPlanning.mrp.available') }}</div>
              </v-card-text>
            </v-card>
          </v-col>
          <v-col cols="4">
            <v-card variant="tonal" color="error">
              <v-card-text class="text-center">
                <div class="text-h4">{{ results.shortage_count || 0 }}</div>
                <div class="text-subtitle-1">{{ t('capacityPlanning.mrp.shortages') }}</div>
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
          <strong>{{ t('capacityPlanning.mrp.shortageAlert', { count: results.shortage_count }) }}</strong>
          {{ t('capacityPlanning.mrp.shortageActionPrompt') }}
        </v-alert>

        <!-- Component Details -->
        <v-expansion-panels v-if="results.components?.length">
          <v-expansion-panel :title="t('capacityPlanning.mrp.shortages')" v-if="shortages.length">
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
                    {{ t('capacityPlanning.mrp.required') }}: {{ item.required_quantity }} | {{ t('capacityPlanning.mrp.available') }}: {{ item.available_quantity }} |
                    <strong class="text-error">{{ t('capacityPlanning.mrp.short') }}: {{ item.shortage_quantity }}</strong>
                  </v-list-item-subtitle>
                </v-list-item>
              </v-list>
            </v-expansion-panel-text>
          </v-expansion-panel>

          <v-expansion-panel :title="t('capacityPlanning.mrp.partialAvailability')" v-if="partials.length">
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
                    {{ t('capacityPlanning.mrp.required') }}: {{ item.required_quantity }} | {{ t('capacityPlanning.mrp.available') }}: {{ item.available_quantity }}
                  </v-list-item-subtitle>
                </v-list-item>
              </v-list>
            </v-expansion-panel-text>
          </v-expansion-panel>

          <v-expansion-panel :title="t('capacityPlanning.mrp.availableComponents')">
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
                    {{ t('capacityPlanning.mrp.required') }}: {{ item.required_quantity }} | {{ t('capacityPlanning.mrp.available') }}: {{ item.available_quantity }}
                  </v-list-item-subtitle>
                </v-list-item>
              </v-list>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>

        <!-- No Results -->
        <div v-else class="text-center pa-4 text-grey">
          {{ t('capacityPlanning.mrp.noComponentData') }}
        </div>
      </v-card-text>
      <v-card-text v-else class="text-center pa-8 text-grey">
        {{ t('capacityPlanning.mrp.noMrpResults') }}
      </v-card-text>
      <v-card-actions>
        <v-btn variant="tonal" @click="exportResults">
          <v-icon start>mdi-download</v-icon>
          {{ t('capacityPlanning.mrp.exportResults') }}
        </v-btn>
        <v-spacer />
        <v-btn color="primary" @click="$emit('close')">{{ t('common.close') }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

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
