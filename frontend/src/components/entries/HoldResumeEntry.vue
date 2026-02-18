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
import { onMounted } from 'vue'
import CSVUploadDialogHold from '@/components/CSVUploadDialogHold.vue'
import ReadBackConfirmation from '@/components/dialogs/ReadBackConfirmation.vue'
import { useHoldResumeData } from '@/composables/useHoldResumeData'

const emit = defineEmits(['submitted'])

const {
  tab,
  holdForm,
  resumeForm,
  holdValid,
  resumeValid,
  loading,
  initialLoading,
  workOrders,
  activeHolds,
  selectedHoldId,
  selectedHold,
  showHoldConfirmDialog,
  showResumeConfirmDialog,
  snackbar,
  holdReasons,
  severities,
  dispositions,
  holdData,
  resumeData,
  rules,
  holdConfirmationFieldConfig,
  resumeConfirmData,
  resumeConfirmationFieldConfig,
  formatDate,
  loadActiveHolds,
  loadHoldDetails,
  onImported,
  submitHold,
  onConfirmHold,
  onCancelHold,
  submitResume,
  onConfirmResume,
  onCancelResume
} = useHoldResumeData(emit)

onMounted(() => {
  loadActiveHolds()
  // Load work orders placeholder
  workOrders.value = []
})
</script>
