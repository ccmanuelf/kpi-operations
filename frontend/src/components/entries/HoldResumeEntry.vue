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
                  item-title="title"
                  item-value="value"
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
                  item-title="title"
                  item-value="value"
                  :label="`${$t('holds.severity')} *`"
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
                  :label="`${$t('holds.holdDescription')} *`"
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
                  :label="$t('holds.requiredAction')"
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
                  :label="$t('holds.initiatedBy')"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>
              <v-col cols="12" md="6">
                <v-checkbox
                  v-model="holdData.customer_notification_required"
                  :label="$t('holds.customerNotificationRequired')"
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
                :label="`${$t('holds.selectHoldToResume')} *`"
                variant="outlined"
                density="comfortable"
                @update:model-value="loadHoldDetails"
              />
            </v-col>
          </v-row>

          <v-row v-if="selectedHold">
            <v-col cols="12">
              <v-alert type="warning" variant="tonal" class="mb-4">
                <div class="text-subtitle-2">{{ $t('holds.holdInformation') }}</div>
                <div class="text-caption mt-2">
                  <strong>{{ $t('production.workOrder') }}:</strong> {{ selectedHold.work_order }}<br>
                  <strong>{{ $t('workOrders.quantity') }}:</strong> {{ selectedHold.quantity }}<br>
                  <strong>{{ $t('holds.holdReason') }}:</strong> {{ selectedHold.reason }}<br>
                  <strong>{{ $t('holds.holdDescription') }}:</strong> {{ selectedHold.description }}<br>
                  <strong>{{ $t('holds.holdDate') }}:</strong> {{ formatDate(selectedHold.hold_date) }}
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
                  item-title="title"
                  item-value="value"
                  :label="`${$t('holds.disposition')} *`"
                  :rules="[rules.required]"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model.number="resumeData.released_quantity"
                  type="number"
                  :label="$t('holds.releasedQuantity')"
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
                  :label="`${$t('holds.resolutionNotes')} *`"
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
                  :label="`${$t('holds.approvedBy')} *`"
                  :rules="[rules.required]"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>
              <v-col cols="12" md="6">
                <v-checkbox
                  v-model="resumeData.customer_notified"
                  :label="$t('holds.customerNotified')"
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

    <!-- Read-Back Confirmation Dialog for Hold -->
    <ReadBackConfirmation
      v-model="showHoldConfirmDialog"
      :title="$t('readBack.confirmEntry')"
      :subtitle="$t('readBack.verifyBeforeSaving')"
      :data="holdData"
      :field-config="holdConfirmationFieldConfig"
      :loading="loading"
      @confirm="onConfirmHold"
      @cancel="onCancelHold"
    />

    <!-- Read-Back Confirmation Dialog for Resume -->
    <ReadBackConfirmation
      v-model="showResumeConfirmDialog"
      :title="$t('readBack.confirmEntry')"
      :subtitle="$t('readBack.verifyBeforeSaving')"
      :data="resumeConfirmData"
      :field-config="resumeConfirmationFieldConfig"
      :loading="loading"
      @confirm="onConfirmResume"
      @cancel="onCancelResume"
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
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { format } from 'date-fns'
import api from '@/services/api'
import CSVUploadDialogHold from '@/components/CSVUploadDialogHold.vue'
import ReadBackConfirmation from '@/components/dialogs/ReadBackConfirmation.vue'

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
const showHoldConfirmDialog = ref(false)
const showResumeConfirmDialog = ref(false)
const snackbar = ref({ show: false, text: '', color: 'info' })

const holdReasons = computed(() => [
  { title: t('holds.reasons.qualityIssue'), value: 'Quality Issue' },
  { title: t('holds.reasons.materialDefect'), value: 'Material Defect' },
  { title: t('holds.reasons.processNonConformance'), value: 'Process Non-Conformance' },
  { title: t('holds.reasons.customerRequest'), value: 'Customer Request' },
  { title: t('holds.reasons.engineeringChange'), value: 'Engineering Change' },
  { title: t('holds.reasons.inspectionFailure'), value: 'Inspection Failure' },
  { title: t('holds.reasons.supplierIssue'), value: 'Supplier Issue' },
  { title: t('holds.reasons.other'), value: 'Other' }
])

const severities = computed(() => [
  { title: t('holds.severities.critical'), value: 'Critical' },
  { title: t('holds.severities.high'), value: 'High' },
  { title: t('holds.severities.medium'), value: 'Medium' },
  { title: t('holds.severities.low'), value: 'Low' }
])
const dispositions = computed(() => [
  { title: t('holds.dispositions.release'), value: 'Release' },
  { title: t('holds.dispositions.rework'), value: 'Rework' },
  { title: t('holds.dispositions.scrap'), value: 'Scrap' },
  { title: t('holds.dispositions.returnToSupplier'), value: 'Return to Supplier' },
  { title: t('holds.dispositions.useAsIs'), value: 'Use As Is' }
])

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

// Field configuration for hold confirmation dialog
const holdConfirmationFieldConfig = computed(() => {
  const workOrderName = workOrders.value.find(w => w.id === holdData.value.work_order_id)?.work_order || 'N/A'

  return [
    { key: 'work_order_id', label: t('production.workOrder'), type: 'text', displayValue: workOrderName },
    { key: 'quantity', label: t('workOrders.quantity'), type: 'number' },
    { key: 'reason', label: t('holds.holdReason'), type: 'text' },
    { key: 'severity', label: t('holds.severity'), type: 'text' },
    { key: 'description', label: t('holds.holdDescription'), type: 'text' },
    { key: 'required_action', label: t('holds.requiredAction'), type: 'text' },
    { key: 'initiated_by', label: t('holds.initiatedBy'), type: 'text' },
    { key: 'customer_notification_required', label: t('holds.customerNotificationRequired'), type: 'boolean' }
  ]
})

// Combined data for resume confirmation
const resumeConfirmData = computed(() => ({
  work_order: selectedHold.value?.work_order || 'N/A',
  original_quantity: selectedHold.value?.quantity || 0,
  hold_reason: selectedHold.value?.reason || 'N/A',
  ...resumeData.value
}))

// Field configuration for resume confirmation dialog
const resumeConfirmationFieldConfig = computed(() => {
  return [
    { key: 'work_order', label: t('production.workOrder'), type: 'text' },
    { key: 'original_quantity', label: t('holds.originalQuantity'), type: 'number' },
    { key: 'hold_reason', label: t('holds.originalHoldReason'), type: 'text' },
    { key: 'disposition', label: t('holds.disposition'), type: 'text' },
    { key: 'released_quantity', label: t('holds.releasedQuantity'), type: 'number' },
    { key: 'resolution_notes', label: t('holds.resolutionNotes'), type: 'text' },
    { key: 'approved_by', label: t('holds.approvedBy'), type: 'text' },
    { key: 'customer_notified', label: t('holds.customerNotified'), type: 'boolean' }
  ]
})

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

  // Show read-back confirmation dialog
  showHoldConfirmDialog.value = true
}

const onConfirmHold = async () => {
  showHoldConfirmDialog.value = false
  loading.value = true

  try {
    await api.createHoldEntry(holdData.value)

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
    snackbar.value = {
      show: true,
      text: t('holds.errors.createHold') + ': ' + (error.response?.data?.detail || error.message),
      color: 'error'
    }
  } finally {
    loading.value = false
  }
}

const onCancelHold = () => {
  showHoldConfirmDialog.value = false
}

const submitResume = async () => {
  const { valid: isValid } = await resumeForm.value.validate()
  if (!isValid || !selectedHoldId.value) return

  // Show read-back confirmation dialog
  showResumeConfirmDialog.value = true
}

const onConfirmResume = async () => {
  showResumeConfirmDialog.value = false
  loading.value = true

  try {
    await api.resumeHold(selectedHoldId.value, resumeData.value)

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
    snackbar.value = {
      show: true,
      text: t('holds.errors.resumeHold') + ': ' + (error.response?.data?.detail || error.message),
      color: 'error'
    }
  } finally {
    loading.value = false
  }
}

const onCancelResume = () => {
  showResumeConfirmDialog.value = false
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
