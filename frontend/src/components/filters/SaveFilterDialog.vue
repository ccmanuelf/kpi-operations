<template>
  <v-dialog v-model="isOpen" max-width="500" persistent>
    <v-card>
      <v-card-title class="d-flex align-center pa-4 bg-primary">
        <v-icon class="mr-2">mdi-content-save-plus</v-icon>
        <span class="text-h6">Save Filter</span>
        <v-spacer></v-spacer>
        <v-btn icon variant="text" @click="cancel">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>

      <v-card-text class="pa-4">
        <v-form ref="formRef" v-model="isFormValid" @submit.prevent="save">
          <!-- Filter Name -->
          <v-text-field
            v-model="filterName"
            :label="t('filters.filterName')"
            placeholder="e.g., Q1 Production Overview"
            variant="outlined"
            density="comfortable"
            :rules="nameRules"
            :error-messages="nameError"
            autofocus
            class="mb-4"
          >
            <template #prepend-inner>
              <v-icon size="small">mdi-label-outline</v-icon>
            </template>
          </v-text-field>

          <!-- Filter Type -->
          <v-select
            v-model="filterType"
            :items="filterTypeOptions"
            item-title="label"
            item-value="value"
            :label="t('filters.filterType')"
            variant="outlined"
            density="comfortable"
            :rules="[(v) => !!v || 'Filter type is required']"
            class="mb-4"
          >
            <template #prepend-inner>
              <v-icon size="small">mdi-tag-outline</v-icon>
            </template>
            <template #item="{ item, props: itemProps }">
              <v-list-item v-bind="itemProps">
                <template #prepend>
                  <v-icon size="small">{{ getTypeIcon(item.value) }}</v-icon>
                </template>
              </v-list-item>
            </template>
          </v-select>

          <!-- Set as Default -->
          <v-checkbox
            v-model="isDefault"
            density="compact"
            color="primary"
            class="mb-4"
          >
            <template #label>
              <div>
                <span>Set as default for {{ FILTER_TYPES[filterType] || 'this type' }}</span>
                <div class="text-caption text-medium-emphasis">
                  This filter will be automatically applied when you visit this section
                </div>
              </div>
            </template>
          </v-checkbox>

          <!-- Filter Preview -->
          <v-expansion-panels variant="accordion" class="mb-2">
            <v-expansion-panel>
              <v-expansion-panel-title>
                <v-icon start size="small">mdi-eye-outline</v-icon>
                Filter Configuration Preview
              </v-expansion-panel-title>
              <v-expansion-panel-text>
                <div class="filter-preview pa-3 rounded bg-grey-lighten-4">
                  <!-- Friendly preview -->
                  <v-list density="compact" class="bg-transparent pa-0">
                    <v-list-item v-if="filterConfig.client_id" class="px-0">
                      <template #prepend>
                        <v-icon size="small" color="primary">mdi-domain</v-icon>
                      </template>
                      <v-list-item-title class="text-body-2">
                        Client: {{ getClientName(filterConfig.client_id) }}
                      </v-list-item-title>
                    </v-list-item>

                    <v-list-item v-if="filterConfig.date_range" class="px-0">
                      <template #prepend>
                        <v-icon size="small" color="success">mdi-calendar</v-icon>
                      </template>
                      <v-list-item-title class="text-body-2">
                        {{ formatDateRange(filterConfig.date_range) }}
                      </v-list-item-title>
                    </v-list-item>

                    <v-list-item v-if="filterConfig.shift_ids?.length" class="px-0">
                      <template #prepend>
                        <v-icon size="small" color="warning">mdi-clock-outline</v-icon>
                      </template>
                      <v-list-item-title class="text-body-2">
                        {{ filterConfig.shift_ids.length }} Shift(s) selected
                      </v-list-item-title>
                    </v-list-item>

                    <v-list-item v-if="filterConfig.product_ids?.length" class="px-0">
                      <template #prepend>
                        <v-icon size="small" color="info">mdi-package-variant</v-icon>
                      </template>
                      <v-list-item-title class="text-body-2">
                        {{ filterConfig.product_ids.length }} Product(s) selected
                      </v-list-item-title>
                    </v-list-item>

                    <v-list-item v-if="!hasAnyConfig" class="px-0">
                      <template #prepend>
                        <v-icon size="small" color="grey">mdi-information-outline</v-icon>
                      </template>
                      <v-list-item-title class="text-body-2 text-medium-emphasis">
                        No specific filters configured (shows all data)
                      </v-list-item-title>
                    </v-list-item>
                  </v-list>

                  <!-- Raw JSON toggle -->
                  <v-btn
                    size="x-small"
                    variant="text"
                    class="mt-2"
                    @click="showRawJson = !showRawJson"
                  >
                    {{ showRawJson ? 'Hide' : 'Show' }} Raw JSON
                  </v-btn>

                  <v-expand-transition>
                    <pre v-if="showRawJson" class="text-caption mt-2 pa-2 bg-grey-darken-4 rounded overflow-auto" style="max-height: 150px">{{ JSON.stringify(filterConfig, null, 2) }}</pre>
                  </v-expand-transition>
                </div>
              </v-expansion-panel-text>
            </v-expansion-panel>
          </v-expansion-panels>
        </v-form>
      </v-card-text>

      <v-divider></v-divider>

      <v-card-actions class="pa-4">
        <v-btn
          variant="text"
          @click="cancel"
        >
          Cancel
        </v-btn>
        <v-spacer></v-spacer>
        <v-btn
          color="primary"
          variant="flat"
          :loading="isSaving"
          :disabled="!isFormValid || !filterName"
          @click="save"
        >
          <v-icon start>mdi-content-save</v-icon>
          Save Filter
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useFiltersStore, FILTER_TYPES } from '@/stores/filtersStore'
import api from '@/services/api'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  filterConfig: {
    type: Object,
    default: () => ({})
  },
  suggestedType: {
    type: String,
    default: 'dashboard'
  }
})

const emit = defineEmits(['update:modelValue', 'saved'])

const { t } = useI18n()
const filtersStore = useFiltersStore()

// Form state
const formRef = ref(null)
const isFormValid = ref(false)
const filterName = ref('')
const filterType = ref(props.suggestedType)
const isDefault = ref(false)
const isSaving = ref(false)
const nameError = ref('')
const showRawJson = ref(false)
const clients = ref([])

// Dialog state
const isOpen = ref(props.modelValue)

// Validation rules
const nameRules = [
  (v) => !!v || 'Filter name is required',
  (v) => (v && v.length >= 2) || 'Name must be at least 2 characters',
  (v) => (v && v.length <= 100) || 'Name must be less than 100 characters'
]

// Filter type options for select
const filterTypeOptions = computed(() => {
  return Object.entries(FILTER_TYPES).map(([value, label]) => ({
    value,
    label
  }))
})

// Check if config has any values
const hasAnyConfig = computed(() => {
  const config = props.filterConfig
  return (
    config.client_id ||
    config.shift_ids?.length > 0 ||
    config.product_ids?.length > 0 ||
    (config.date_range?.type === 'absolute') ||
    (config.date_range?.relative_days && config.date_range.relative_days !== 30)
  )
})

// Methods
const getTypeIcon = (type) => {
  const icons = {
    dashboard: 'mdi-view-dashboard',
    production: 'mdi-factory',
    quality: 'mdi-check-decagram',
    attendance: 'mdi-account-clock',
    downtime: 'mdi-clock-alert',
    hold: 'mdi-pause-circle',
    coverage: 'mdi-shield-check'
  }
  return icons[type] || 'mdi-filter'
}

const getClientName = (clientId) => {
  const client = clients.value.find(c => c.client_id === clientId)
  return client?.client_name || `Client #${clientId}`
}

const formatDateRange = (dateRange) => {
  if (!dateRange) return 'All dates'

  if (dateRange.type === 'relative' && dateRange.relative_days) {
    if (dateRange.relative_days === 0) return 'Today'
    if (dateRange.relative_days === 7) return 'Last 7 days'
    if (dateRange.relative_days === 30) return 'Last 30 days'
    if (dateRange.relative_days === 90) return 'Last 90 days'
    return `Last ${dateRange.relative_days} days`
  }

  if (dateRange.type === 'absolute') {
    return `${dateRange.start_date} to ${dateRange.end_date}`
  }

  return 'All dates'
}

const save = async () => {
  if (!isFormValid.value) return

  isSaving.value = true
  nameError.value = ''

  try {
    const filterData = {
      filter_name: filterName.value.trim(),
      filter_type: filterType.value,
      filter_config: props.filterConfig,
      is_default: isDefault.value
    }

    const savedFilter = await filtersStore.createFilter(filterData)

    if (savedFilter) {
      emit('saved', savedFilter)
      close()
      resetForm()
    }
  } catch (error) {
    if (error.response?.data?.detail) {
      nameError.value = error.response.data.detail
    } else {
      nameError.value = 'Failed to save filter. Please try again.'
    }
  } finally {
    isSaving.value = false
  }
}

const cancel = () => {
  close()
  resetForm()
}

const close = () => {
  isOpen.value = false
}

const resetForm = () => {
  filterName.value = ''
  filterType.value = props.suggestedType
  isDefault.value = false
  nameError.value = ''
  showRawJson.value = false
  formRef.value?.reset()
}

const loadClients = async () => {
  try {
    const response = await api.getClients()
    clients.value = response.data || []
  } catch (e) {
    console.error('Failed to load clients:', e)
  }
}

// Watch dialog visibility
watch(() => props.modelValue, (newValue) => {
  isOpen.value = newValue
})

watch(isOpen, (newValue) => {
  emit('update:modelValue', newValue)
  if (newValue) {
    filterType.value = props.suggestedType
  }
})

// Initialize
onMounted(() => {
  loadClients()
})
</script>

<style scoped>
.filter-preview pre {
  white-space: pre-wrap;
  word-break: break-word;
  color: #e0e0e0;
}

.v-theme--light .filter-preview pre {
  background-color: #263238 !important;
}
</style>
