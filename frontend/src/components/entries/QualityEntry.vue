<template>
  <v-skeleton-loader
    v-if="initialLoading"
    type="card, article, actions"
    class="mb-4"
  />
  <v-card v-else>
    <v-card-title class="d-flex justify-space-between align-center">
      <div>
        <v-icon class="mr-2">mdi-clipboard-check</v-icon>
        {{ $t('quality.entry') }}
      </div>
      <CSVUploadDialogQuality @imported="onImported" />
    </v-card-title>
    <v-card-text>
      <v-form ref="form" v-model="valid">
        <v-row>
          <v-col cols="12" md="4">
            <v-select
              v-model="formData.client_id"
              :items="clients"
              item-title="client_name"
              item-value="client_id"
              :label="`${$t('workOrders.client')} *`"
              :rules="[rules.required]"
              variant="outlined"
              density="comfortable"
            />
          </v-col>
          <v-col cols="12" md="4">
            <v-select
              v-model="formData.work_order_id"
              :items="workOrders"
              item-title="work_order"
              item-value="id"
              :label="`${$t('production.workOrder')} *`"
              :rules="[rules.required]"
              variant="outlined"
              density="comfortable"
            />
          </v-col>
          <v-col cols="12" md="4">
            <v-select
              v-model="formData.product_id"
              :items="products"
              item-title="name"
              item-value="id"
              :label="`${$t('workOrders.product')} *`"
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
              :label="`${$t('quality.inspectedQty')} *`"
              :rules="[rules.required, rules.positive]"
              variant="outlined"
              density="comfortable"
            />
          </v-col>
          <v-col cols="12" md="4">
            <v-text-field
              v-model.number="formData.defect_quantity"
              type="number"
              :label="$t('quality.defectQty')"
              variant="outlined"
              density="comfortable"
            />
          </v-col>
          <v-col cols="12" md="4">
            <v-text-field
              v-model.number="formData.rejected_quantity"
              type="number"
              :label="$t('quality.rejectedQty')"
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
              item-title="defect_name"
              item-value="defect_type_id"
              :label="$t('quality.primaryDefectType')"
              variant="outlined"
              density="comfortable"
              :disabled="!formData.client_id"
              :hint="!formData.client_id ? $t('quality.selectClientFirst') : ''"
              persistent-hint
            />
          </v-col>
          <v-col cols="12" md="6">
            <v-select
              v-model="formData.severity"
              :items="severities"
              item-title="title"
              item-value="value"
              :label="$t('quality.severity')"
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
              item-title="title"
              item-value="value"
              :label="`${$t('quality.disposition')} *`"
              :rules="[rules.required]"
              variant="outlined"
              density="comfortable"
            />
          </v-col>
          <v-col cols="12" md="6">
            <v-text-field
              v-model="formData.inspector_id"
              :label="$t('quality.inspectorId')"
              variant="outlined"
              density="comfortable"
            />
          </v-col>
        </v-row>

        <v-row>
          <v-col cols="12">
            <v-textarea
              v-model="formData.defect_description"
              :label="$t('quality.defectDescription')"
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
              :label="$t('quality.correctiveAction')"
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
              <div class="text-subtitle-2">{{ $t('quality.calculatedMetrics') }}</div>
              <v-row class="mt-2">
                <v-col cols="6" md="3">
                  <div class="text-caption">FPY</div>
                  <div class="text-h6">{{ calculateFPY() }}%</div>
                </v-col>
                <v-col cols="6" md="3">
                  <div class="text-caption">{{ $t('quality.defectRate') }}</div>
                  <div class="text-h6">{{ calculateDefectRate() }}%</div>
                </v-col>
                <v-col cols="6" md="3">
                  <div class="text-caption">PPM</div>
                  <div class="text-h6">{{ calculatePPM() }}</div>
                </v-col>
                <v-col cols="6" md="3">
                  <div class="text-caption">{{ $t('quality.passQty') }}</div>
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
        {{ $t('common.submit') }} {{ $t('quality.entry') }}
      </v-btn>
    </v-card-actions>

    <!-- Read-Back Confirmation Dialog -->
    <ReadBackConfirmation
      v-model="showConfirmDialog"
      :title="$t('readBack.confirmEntry')"
      :subtitle="$t('readBack.verifyBeforeSaving')"
      :data="formData"
      :field-config="confirmationFieldConfig"
      :loading="loading"
      @confirm="onConfirmSave"
      @cancel="onCancelSave"
    />

    <!-- Snackbar -->
    <v-snackbar
      v-model="snackbar.show"
      :color="snackbar.color"
      :timeout="3000"
    >
      {{ snackbar.text }}
    </v-snackbar>
  </v-card>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/services/api'
import CSVUploadDialogQuality from '@/components/CSVUploadDialogQuality.vue'
import ReadBackConfirmation from '@/components/dialogs/ReadBackConfirmation.vue'
import { useKPIStore } from '@/stores/kpi'

const { t } = useI18n()

const emit = defineEmits(['submitted'])
const kpiStore = useKPIStore()

const form = ref(null)
const valid = ref(false)
const loading = ref(false)
const initialLoading = ref(true)
const products = ref([])
const defectTypes = ref([])
const workOrders = ref([])
const clients = ref([])
const showConfirmDialog = ref(false)
const snackbar = ref({ show: false, text: '', color: 'info' })

const severities = computed(() => [
  { title: t('quality.severities.critical'), value: 'Critical' },
  { title: t('quality.severities.major'), value: 'Major' },
  { title: t('quality.severities.minor'), value: 'Minor' },
  { title: t('quality.severities.cosmetic'), value: 'Cosmetic' }
])
const dispositions = computed(() => [
  { title: t('quality.dispositions.accept'), value: 'Accept' },
  { title: t('quality.dispositions.reject'), value: 'Reject' },
  { title: t('quality.dispositions.rework'), value: 'Rework' },
  { title: t('quality.dispositions.useAsIs'), value: 'Use As Is' },
  { title: t('quality.dispositions.returnToSupplier'), value: 'Return to Supplier' }
])

const formData = ref({
  client_id: null,
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
  required: value => !!value || t('validation.required'),
  positive: value => value > 0 || t('validation.positive')
}

// Field configuration for confirmation dialog
const confirmationFieldConfig = computed(() => {
  const clientName = clients.value.find(c => c.client_id === formData.value.client_id)?.client_name || 'N/A'
  const productName = products.value.find(p => p.id === formData.value.product_id)?.name || 'N/A'
  const workOrderName = workOrders.value.find(w => w.id === formData.value.work_order_id)?.work_order || 'N/A'
  const defectTypeName = defectTypes.value.find(d => d.defect_type_id === formData.value.defect_type_id)?.defect_name || 'N/A'

  return [
    { key: 'client_id', label: t('workOrders.client'), type: 'text', displayValue: clientName },
    { key: 'work_order_id', label: t('production.workOrder'), type: 'text', displayValue: workOrderName },
    { key: 'product_id', label: t('workOrders.product'), type: 'text', displayValue: productName },
    { key: 'inspected_quantity', label: t('quality.inspectedQty'), type: 'number' },
    { key: 'defect_quantity', label: t('quality.defectQty'), type: 'number' },
    { key: 'rejected_quantity', label: t('quality.rejectedQty'), type: 'number' },
    { key: 'defect_type_id', label: t('quality.primaryDefectType'), type: 'text', displayValue: defectTypeName },
    { key: 'severity', label: t('quality.severity'), type: 'text' },
    { key: 'disposition', label: t('quality.disposition'), type: 'text' },
    { key: 'inspector_id', label: t('quality.inspectorId'), type: 'text' },
    { key: 'defect_description', label: t('quality.defectDescription'), type: 'text' },
    { key: 'corrective_action', label: t('quality.correctiveAction'), type: 'text' }
  ]
})

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

  // Show read-back confirmation dialog
  showConfirmDialog.value = true
}

const onConfirmSave = async () => {
  showConfirmDialog.value = false
  loading.value = true

  try {
    await api.createQualityEntry(formData.value)

    formData.value = {
      client_id: null,
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
    snackbar.value = {
      show: true,
      text: t('quality.errors.createEntry') + ': ' + (error.response?.data?.detail || error.message),
      color: 'error'
    }
  } finally {
    loading.value = false
  }
}

const onCancelSave = () => {
  showConfirmDialog.value = false
}

const loadReferenceData = async () => {
  try {
    const [productsRes, clientsRes] = await Promise.all([
      api.getProducts(),
      api.getClients()
    ])
    products.value = productsRes.data
    clients.value = clientsRes.data || []

    // Load defect types for selected client
    await loadDefectTypes()

    // Load work orders (placeholder)
    workOrders.value = []
  } catch (error) {
    console.error('Error loading reference data:', error)
  } finally {
    initialLoading.value = false
  }
}

const loadDefectTypes = async () => {
  try {
    const clientId = formData.value.client_id || kpiStore.selectedClient || clients.value[0]?.client_id
    if (clientId) {
      const res = await api.getDefectTypes(clientId)
      defectTypes.value = res.data || []
    } else {
      defectTypes.value = []
    }
  } catch (error) {
    console.error('Error loading defect types:', error)
    defectTypes.value = []
  }
}

// Watch for client changes to reload defect types
watch(() => formData.value.client_id, async (newClientId) => {
  if (newClientId) {
    await loadDefectTypes()
    // Reset defect type selection when client changes
    formData.value.defect_type_id = null
  }
})

onMounted(() => {
  loadReferenceData()
})
</script>
