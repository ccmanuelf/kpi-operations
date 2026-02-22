<template>
  <v-autocomplete
    :model-value="modelValue"
    @update:model-value="$emit('update:modelValue', $event)"
    :items="lineItems"
    item-title="text"
    item-value="value"
    :label="label || $t('productionLines.label')"
    :loading="loading"
    :clearable="clearable"
    :disabled="disabled"
    variant="outlined"
    density="compact"
    hide-details
    :no-data-text="$t('productionLines.noLines')"
  >
    <template v-slot:prepend-inner>
      <v-icon size="small">mdi-factory</v-icon>
    </template>
  </v-autocomplete>
</template>

<script setup>
import { computed, onMounted, watch } from 'vue'
import { useProductionLines } from '@/composables/useProductionLines'

const props = defineProps({
  modelValue: {
    type: [Number, String, null],
    default: null
  },
  clientId: {
    type: [Number, String, null],
    default: null
  },
  label: {
    type: String,
    default: ''
  },
  clearable: {
    type: Boolean,
    default: true
  },
  disabled: {
    type: Boolean,
    default: false
  }
})

defineEmits(['update:modelValue'])

const { lines, loading, fetchLines } = useProductionLines(computed(() => props.clientId))

const lineItems = computed(() => {
  return lines.value.map(line => ({
    text: line.line_code
      ? `${line.line_name} (${line.line_code})`
      : line.line_name || line.name || `Line ${line.line_id || line.id}`,
    value: line.line_id || line.id
  }))
})

onMounted(() => {
  fetchLines()
})

watch(() => props.clientId, () => {
  fetchLines()
})
</script>
