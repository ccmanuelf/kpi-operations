<template>
  <v-skeleton-loader
    v-if="initialLoading"
    type="card, table, actions"
    class="mb-4"
  />
  <v-card v-else>
    <v-card-title class="d-flex justify-space-between align-center">
      <div>
        <v-icon class="mr-2">mdi-pause-circle</v-icon>
        {{ $t('navigation.holdResume') }}
      </div>
      <CSVUploadDialogHold @imported="onImported" />
    </v-card-title>
    <v-card-text>
      <v-tabs v-model="tab" class="mb-4">
        <v-tab value="hold">{{ $t('common.add') }} {{ $t('holds.title') }}</v-tab>
        <v-tab value="resume">{{ $t('holds.resumed') }}</v-tab>
      </v-tabs>

      <v-window v-model="tab">
        <!-- Create Hold Tab -->
        <v-window-item value="hold">
          <v-form ref="holdForm" v-model="holdValid">
            <v-row>
              <v-col cols="12" md="6">
                <v-select
                  v-model="holdData.work_order_id"
                  :items="workOrders"
                  item-title="work_order"
                  item-value="id"
                  :label="`${$t('production.workOrder')} *`"
                  :rules="[rules.required]"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model.number="holdData.quantity"
                  type="number"
                  :label="`${$t('workOrders.quantity')} *`"
                  :rules="[rules.required, rules.positive]"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>
            </v-row>

            <v-row>
              <v-col cols="12" md="6">
                <v-select
                  v-model="holdData.reason"
                  :items="holdReasons"
                  :label="`${$t('holds.holdReason')} *`"
                  :rules="[rules.required]"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>
              <v-col cols="12" md="6">
                <v-select
                  v-model="holdData.severity"
                  :items="severities"
                  label="Severity *"
                  :rules="[rules.required]"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>
            </v-row>

            <v-row>
              <v-col cols="12">
                <v-textarea
                  v-model="holdData.description"
                  label="Hold Description *"
                  :rules="[rules.required]"
                  rows="3"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>
            </v-row>

            <v-row>
              <v-col cols="12">
                <v-textarea
                  v-model="holdData.required_action"
                  label="Required Action for Release"
                  rows="3"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>
            </v-row>

            <v-row>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="holdData.initiated_by"
                  label="Initiated By"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>
              <v-col cols="12" md="6">
                <v-checkbox
                  v-model="holdData.customer_notification_required"
                  label="Customer Notification Required"
                  density="comfortable"
                />
              </v-col>
            </v-row>
          </v-form>
        </v-window-item>

        <!-- Resume Hold Tab -->
        <v-window-item value="resume">
          <v-row>
            <v-col cols="12">
              <v-select
                v-model="selectedHoldId"
                :items="activeHolds"
                item-title="display"
                item-value="id"
                label="Select Hold to Resume *"
                variant="outlined"
                density="comfortable"
                @update:model-value="loadHoldDetails"
              />
            </v-col>
          </v-row>

          <v-row v-if="selectedHold">
            <v-col cols="12">
              <v-alert type="warning" variant="tonal" class="mb-4">
                <div class="text-subtitle-2">Hold Information</div>
                <div class="text-caption mt-2">
                  <strong>Work Order:</strong> {{ selectedHold.work_order }}<br>
                  <strong>Quantity:</strong> {{ selectedHold.quantity }}<br>
                  <strong>Reason:</strong> {{ selectedHold.reason }}<br>
                  <strong>Description:</strong> {{ selectedHold.description }}<br>
                  <strong>Hold Date:</strong> {{ formatDate(selectedHold.hold_date) }}
                </div>
              </v-alert>
            </v-col>
          </v-row>

          <v-form ref="resumeForm" v-model="resumeValid">
            <v-row>
              <v-col cols="12" md="6">
                <v-select
                  v-model="resumeData.disposition"
                  :items="dispositions"
                  label="Disposition *"
                  :rules="[rules.required]"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model.number="resumeData.released_quantity"
                  type="number"
                  label="Released Quantity"
                  :max="selectedHold?.quantity"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>
            </v-row>

            <v-row>
              <v-col cols="12">
                <v-textarea
                  v-model="resumeData.resolution_notes"
                  label="Resolution Notes *"
                  :rules="[rules.required]"
                  rows="3"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>
            </v-row>

            <v-row>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="resumeData.approved_by"
                  label="Approved By *"
                  :rules="[rules.required]"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>
              <v-col cols="12" md="6">
                <v-checkbox
                  v-model="resumeData.customer_notified"
                  label="Customer Notified"
                  density="comfortable"
                />
              </v-col>
            </v-row>
          </v-form>
        </v-window-item>
      </v-window>
    </v-card-text>
    <v-card-actions>
      <v-spacer />
      <v-btn
        v-if="tab === 'hold'"
        color="warning"
        :disabled="!holdValid"
        :loading="loading"
        @click="submitHold"
      >
        {{ $t('common.add') }} {{ $t('holds.title') }}
      </v-btn>
      <v-btn
        v-else
        color="success"
        :disabled="!resumeValid || !selectedHoldId"
        :loading="loading"
        @click="submitResume"
      >
        {{ $t('holds.resumed') }}
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { format } from 'date-fns'
import api from '@/services/api'
import CSVUploadDialogHold from '@/components/CSVUploadDialogHold.vue'

const { t } = useI18n()

const emit = defineEmits(['submitted'])

const tab = ref('hold')
const holdForm = ref(null)
const resumeForm = ref(null)
const holdValid = ref(false)
const resumeValid = ref(false)
const loading = ref(false)
const initialLoading = ref(true)
const workOrders = ref([])
const activeHolds = ref([])
const selectedHoldId = ref(null)
const selectedHold = ref(null)

const holdReasons = [
  'Quality Issue',
  'Material Defect',
  'Process Non-Conformance',
  'Customer Request',
  'Engineering Change',
  'Inspection Failure',
  'Supplier Issue',
  'Other'
]

const severities = ['Critical', 'High', 'Medium', 'Low']
const dispositions = ['Release', 'Rework', 'Scrap', 'Return to Supplier', 'Use As Is']

const holdData = ref({
  work_order_id: null,
  quantity: 0,
  reason: '',
  severity: '',
  description: '',
  required_action: '',
  initiated_by: '',
  customer_notification_required: false
})

const resumeData = ref({
  disposition: '',
  released_quantity: 0,
  resolution_notes: '',
  approved_by: '',
  customer_notified: false
})

const rules = {
  required: value => !!value || t('validation.required'),
  positive: value => value > 0 || t('validation.positive')
}

const onImported = () => {
  loadActiveHolds()
  emit('submitted')
}

const formatDate = (date) => {
  return date ? format(new Date(date), 'MMM dd, yyyy HH:mm') : ''
}

const loadHoldDetails = async () => {
  if (!selectedHoldId.value) return

  const hold = activeHolds.value.find(h => h.id === selectedHoldId.value)
  selectedHold.value = hold
  resumeData.value.released_quantity = hold?.quantity || 0
}

const submitHold = async () => {
  const { valid: isValid } = await holdForm.value.validate()
  if (!isValid) return

  loading.value = true
  try {
    await api.createHoldEntry(holdData.value)

    alert('Hold created successfully!')

    holdData.value = {
      work_order_id: null,
      quantity: 0,
      reason: '',
      severity: '',
      description: '',
      required_action: '',
      initiated_by: '',
      customer_notification_required: false
    }
    holdForm.value.reset()

    await loadActiveHolds()
    emit('submitted')
  } catch (error) {
    alert('Error creating hold: ' + (error.response?.data?.detail || error.message))
  } finally {
    loading.value = false
  }
}

const submitResume = async () => {
  const { valid: isValid } = await resumeForm.value.validate()
  if (!isValid || !selectedHoldId.value) return

  loading.value = true
  try {
    await api.resumeHold(selectedHoldId.value, resumeData.value)

    alert('Hold resumed successfully!')

    selectedHoldId.value = null
    selectedHold.value = null
    resumeData.value = {
      disposition: '',
      released_quantity: 0,
      resolution_notes: '',
      approved_by: '',
      customer_notified: false
    }
    resumeForm.value.reset()

    await loadActiveHolds()
    emit('submitted')
  } catch (error) {
    alert('Error resuming hold: ' + (error.response?.data?.detail || error.message))
  } finally {
    loading.value = false
  }
}

const loadActiveHolds = async () => {
  try {
    const response = await api.getActiveHolds()
    activeHolds.value = response.data.map(hold => ({
      ...hold,
      display: `${hold.work_order} - ${hold.quantity} units (${hold.reason})`
    }))
  } catch (error) {
    console.error('Error loading active holds:', error)
  } finally {
    initialLoading.value = false
  }
}

onMounted(() => {
  loadActiveHolds()
  // Load work orders placeholder
  workOrders.value = []
})
</script>
