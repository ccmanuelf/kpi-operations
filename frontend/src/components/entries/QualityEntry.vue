<template>
  <v-card>
    <v-card-title class="d-flex justify-space-between align-center">
      <div>
        <v-icon class="mr-2">mdi-clipboard-check</v-icon>
        Quality Inspection Entry
      </div>
      <CSVUploadDialogQuality @imported="onImported" />
    </v-card-title>
    <v-card-text>
      <v-form ref="form" v-model="valid">
        <v-row>
          <v-col cols="12" md="6">
            <v-select
              v-model="formData.work_order_id"
              :items="workOrders"
              item-title="work_order"
              item-value="id"
              label="Work Order *"
              :rules="[rules.required]"
              variant="outlined"
              density="comfortable"
            />
          </v-col>
          <v-col cols="12" md="6">
            <v-select
              v-model="formData.product_id"
              :items="products"
              item-title="name"
              item-value="id"
              label="Product *"
              :rules="[rules.required]"
              variant="outlined"
              density="comfortable"
            />
          </v-col>
        </v-row>

        <v-row>
          <v-col cols="12" md="4">
            <v-text-field
              v-model.number="formData.inspected_quantity"
              type="number"
              label="Inspected Quantity *"
              :rules="[rules.required, rules.positive]"
              variant="outlined"
              density="comfortable"
            />
          </v-col>
          <v-col cols="12" md="4">
            <v-text-field
              v-model.number="formData.defect_quantity"
              type="number"
              label="Defect Quantity"
              variant="outlined"
              density="comfortable"
            />
          </v-col>
          <v-col cols="12" md="4">
            <v-text-field
              v-model.number="formData.rejected_quantity"
              type="number"
              label="Rejected Quantity"
              variant="outlined"
              density="comfortable"
            />
          </v-col>
        </v-row>

        <v-row>
          <v-col cols="12" md="6">
            <v-select
              v-model="formData.defect_type_id"
              :items="defectTypes"
              item-title="name"
              item-value="id"
              label="Primary Defect Type"
              variant="outlined"
              density="comfortable"
            />
          </v-col>
          <v-col cols="12" md="6">
            <v-select
              v-model="formData.severity"
              :items="severities"
              label="Severity"
              variant="outlined"
              density="comfortable"
            />
          </v-col>
        </v-row>

        <v-row>
          <v-col cols="12" md="6">
            <v-select
              v-model="formData.disposition"
              :items="dispositions"
              label="Disposition *"
              :rules="[rules.required]"
              variant="outlined"
              density="comfortable"
            />
          </v-col>
          <v-col cols="12" md="6">
            <v-text-field
              v-model="formData.inspector_id"
              label="Inspector ID"
              variant="outlined"
              density="comfortable"
            />
          </v-col>
        </v-row>

        <v-row>
          <v-col cols="12">
            <v-textarea
              v-model="formData.defect_description"
              label="Defect Description"
              rows="3"
              variant="outlined"
              density="comfortable"
            />
          </v-col>
        </v-row>

        <v-row>
          <v-col cols="12">
            <v-textarea
              v-model="formData.corrective_action"
              label="Corrective Action Taken"
              rows="3"
              variant="outlined"
              density="comfortable"
            />
          </v-col>
        </v-row>

        <!-- Calculated Metrics Display -->
        <v-row v-if="formData.inspected_quantity > 0">
          <v-col cols="12">
            <v-alert type="info" variant="tonal">
              <div class="text-subtitle-2">Calculated Metrics</div>
              <v-row class="mt-2">
                <v-col cols="6" md="3">
                  <div class="text-caption">FPY</div>
                  <div class="text-h6">{{ calculateFPY() }}%</div>
                </v-col>
                <v-col cols="6" md="3">
                  <div class="text-caption">Defect Rate</div>
                  <div class="text-h6">{{ calculateDefectRate() }}%</div>
                </v-col>
                <v-col cols="6" md="3">
                  <div class="text-caption">PPM</div>
                  <div class="text-h6">{{ calculatePPM() }}</div>
                </v-col>
                <v-col cols="6" md="3">
                  <div class="text-caption">Pass Qty</div>
                  <div class="text-h6">{{ calculatePassQty() }}</div>
                </v-col>
              </v-row>
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
        Submit Quality Entry
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '@/services/api'
import CSVUploadDialogQuality from '@/components/CSVUploadDialogQuality.vue'

const emit = defineEmits(['submitted'])

const form = ref(null)
const valid = ref(false)
const loading = ref(false)
const products = ref([])
const defectTypes = ref([])
const workOrders = ref([])

const severities = ['Critical', 'Major', 'Minor', 'Cosmetic']
const dispositions = ['Accept', 'Reject', 'Rework', 'Use As Is', 'Return to Supplier']

const formData = ref({
  work_order_id: null,
  product_id: null,
  inspected_quantity: 0,
  defect_quantity: 0,
  rejected_quantity: 0,
  defect_type_id: null,
  severity: '',
  disposition: '',
  inspector_id: '',
  defect_description: '',
  corrective_action: ''
})

const rules = {
  required: value => !!value || 'Field is required',
  positive: value => value > 0 || 'Must be greater than 0'
}

const onImported = () => {
  emit('submitted')
}

const calculateFPY = () => {
  const inspected = formData.value.inspected_quantity || 0
  const defects = formData.value.defect_quantity || 0
  if (inspected === 0) return 0
  return ((1 - defects / inspected) * 100).toFixed(2)
}

const calculateDefectRate = () => {
  const inspected = formData.value.inspected_quantity || 0
  const defects = formData.value.defect_quantity || 0
  if (inspected === 0) return 0
  return ((defects / inspected) * 100).toFixed(2)
}

const calculatePPM = () => {
  const inspected = formData.value.inspected_quantity || 0
  const defects = formData.value.defect_quantity || 0
  if (inspected === 0) return 0
  return Math.round((defects / inspected) * 1000000)
}

const calculatePassQty = () => {
  return (formData.value.inspected_quantity || 0) - (formData.value.defect_quantity || 0)
}

const submitEntry = async () => {
  const { valid: isValid } = await form.value.validate()
  if (!isValid) return

  loading.value = true
  try {
    await api.createQualityEntry(formData.value)

    alert('Quality entry created successfully!')

    formData.value = {
      work_order_id: null,
      product_id: null,
      inspected_quantity: 0,
      defect_quantity: 0,
      rejected_quantity: 0,
      defect_type_id: null,
      severity: '',
      disposition: '',
      inspector_id: '',
      defect_description: '',
      corrective_action: ''
    }
    form.value.reset()

    emit('submitted')
  } catch (error) {
    alert('Error creating quality entry: ' + (error.response?.data?.detail || error.message))
  } finally {
    loading.value = false
  }
}

const loadReferenceData = async () => {
  try {
    const [productsRes, defectTypesRes] = await Promise.all([
      api.getProducts(),
      api.getDefectTypes()
    ])
    products.value = productsRes.data
    defectTypes.value = defectTypesRes.data

    // Load work orders (placeholder)
    workOrders.value = []
  } catch (error) {
    console.error('Error loading reference data:', error)
  }
}

onMounted(() => {
  loadReferenceData()
})
</script>
