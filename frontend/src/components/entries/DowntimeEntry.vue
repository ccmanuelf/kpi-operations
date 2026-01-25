<template>
  <v-skeleton-loader
    v-if="initialLoading"
    type="card, article, actions"
    class="mb-4"
  />
  <v-card v-else>
    <v-card-title class="d-flex justify-space-between align-center">
      <div>
        <v-icon class="mr-2">mdi-alert-circle</v-icon>
        Downtime Entry
      </div>
      <CSVUploadDialogDowntime @imported="onImported" />
    </v-card-title>
    <v-card-text>
      <v-form ref="form" v-model="valid">
        <v-row>
          <v-col cols="12" md="6">
            <v-select
              v-model="formData.equipment_id"
              :items="equipmentList"
              item-title="name"
              item-value="id"
              label="Equipment *"
              :rules="[rules.required]"
              variant="outlined"
              density="comfortable"
            />
          </v-col>
          <v-col cols="12" md="6">
            <v-select
              v-model="formData.reason_id"
              :items="downtimeReasons"
              item-title="name"
              item-value="id"
              label="Downtime Reason *"
              :rules="[rules.required]"
              variant="outlined"
              density="comfortable"
            />
          </v-col>
        </v-row>

        <v-row>
          <v-col cols="12" md="6">
            <v-text-field
              v-model="formData.start_time"
              type="datetime-local"
              label="Start Time *"
              :rules="[rules.required]"
              variant="outlined"
              density="comfortable"
            />
          </v-col>
          <v-col cols="12" md="6">
            <v-text-field
              v-model="formData.end_time"
              type="datetime-local"
              label="End Time"
              variant="outlined"
              density="comfortable"
            />
          </v-col>
        </v-row>

        <v-row>
          <v-col cols="12" md="6">
            <v-text-field
              v-model.number="formData.duration_minutes"
              type="number"
              label="Duration (minutes)"
              variant="outlined"
              density="comfortable"
              readonly
            />
          </v-col>
          <v-col cols="12" md="6">
            <v-select
              v-model="formData.category"
              :items="categories"
              label="Category"
              variant="outlined"
              density="comfortable"
            />
          </v-col>
        </v-row>

        <v-row>
          <v-col cols="12">
            <v-textarea
              v-model="formData.notes"
              label="Notes"
              rows="3"
              variant="outlined"
              density="comfortable"
            />
          </v-col>
        </v-row>

        <v-row v-if="inferenceData">
          <v-col cols="12">
            <v-alert type="info" variant="tonal" class="mb-2">
              <div class="text-subtitle-2">Inference Engine Suggestions</div>
              <div class="text-caption">
                Recommended Category: <strong>{{ inferenceData.category }}</strong>
                (Confidence: {{ (inferenceData.confidence * 100).toFixed(1) }}%)
              </div>
              <v-btn
                size="small"
                variant="text"
                color="primary"
                @click="applySuggestion"
                class="mt-2"
              >
                Apply Suggestion
              </v-btn>
            </v-alert>
          </v-col>
        </v-row>
      </v-form>
    </v-card-text>
    <v-card-actions>
      <v-spacer />
      <v-btn
        color="primary"
        :disabled="!valid"
        :loading="loading"
        @click="submitEntry"
      >
        Submit Downtime Entry
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import api from '@/services/api'
import CSVUploadDialogDowntime from '@/components/CSVUploadDialogDowntime.vue'

const emit = defineEmits(['submitted'])

const form = ref(null)
const valid = ref(false)
const loading = ref(false)
const initialLoading = ref(true)
const equipmentList = ref([])
const downtimeReasons = ref([])
const inferenceData = ref(null)

const categories = [
  'Planned Maintenance',
  'Unplanned Breakdown',
  'Changeover',
  'Material Shortage',
  'Quality Issue',
  'Operator Absence',
  'Other'
]

const formData = ref({
  equipment_id: null,
  reason_id: null,
  start_time: '',
  end_time: '',
  duration_minutes: 0,
  category: '',
  notes: ''
})

const rules = {
  required: value => !!value || 'Field is required'
}

const onImported = () => {
  emit('submitted')
}

// Calculate duration when times change
watch([() => formData.value.start_time, () => formData.value.end_time], ([start, end]) => {
  if (start && end) {
    const startDate = new Date(start)
    const endDate = new Date(end)
    const diffMs = endDate - startDate
    formData.value.duration_minutes = Math.max(0, Math.floor(diffMs / 60000))
  }
})

// Call inference engine when reason changes
watch(() => formData.value.reason_id, async (reasonId) => {
  if (reasonId) {
    try {
      // Placeholder for inference API call
      inferenceData.value = {
        category: 'Unplanned Breakdown',
        confidence: 0.87
      }
    } catch (error) {
      console.error('Inference error:', error)
    }
  }
})

const applySuggestion = () => {
  if (inferenceData.value) {
    formData.value.category = inferenceData.value.category
  }
}

const submitEntry = async () => {
  const { valid: isValid } = await form.value.validate()
  if (!isValid) return

  loading.value = true
  try {
    await api.createDowntimeEntry(formData.value)

    // Show confirmation dialog
    alert('Downtime entry created successfully!')

    // Reset form
    formData.value = {
      equipment_id: null,
      reason_id: null,
      start_time: '',
      end_time: '',
      duration_minutes: 0,
      category: '',
      notes: ''
    }
    form.value.reset()

    emit('submitted')
  } catch (error) {
    alert('Error creating downtime entry: ' + (error.response?.data?.detail || error.message))
  } finally {
    loading.value = false
  }
}

const loadReferenceData = async () => {
  try {
    const [equipmentRes, reasonsRes] = await Promise.all([
      api.getProducts(), // Replace with equipment endpoint
      api.getDowntimeReasons()
    ])
    equipmentList.value = equipmentRes.data
    downtimeReasons.value = reasonsRes.data
  } catch (error) {
    console.error('Error loading reference data:', error)
  } finally {
    initialLoading.value = false
  }
}

onMounted(() => {
  loadReferenceData()
  // Set default start time to now
  const now = new Date()
  formData.value.start_time = now.toISOString().slice(0, 16)
})
</script>
