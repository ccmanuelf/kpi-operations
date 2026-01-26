<template>
  <v-dialog
    v-model="isOpen"
    :fullscreen="isMobile"
    :max-width="isMobile ? undefined : 900"
    persistent
    scrollable
  >
    <v-card class="workflow-wizard">
      <!-- Header -->
      <v-card-title class="d-flex align-center bg-primary text-white pa-4">
        <v-icon class="mr-3" size="28">
          {{ currentWorkflow === 'shift-start' ? 'mdi-play-circle' : 'mdi-stop-circle' }}
        </v-icon>
        <div>
          <div class="text-h6">{{ workflowStore.workflowTitle }}</div>
          <div class="text-caption">Step {{ currentStep + 1 }} of {{ totalSteps }}</div>
        </div>
        <v-spacer />
        <v-btn
          icon
          variant="text"
          color="white"
          @click="handleClose"
          aria-label="Close workflow wizard"
        >
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>

      <!-- Progress Bar -->
      <v-progress-linear
        :model-value="workflowStore.progress"
        color="success"
        height="6"
        aria-label="Workflow progress"
      />

      <!-- Stepper -->
      <v-card-text class="pa-0">
        <v-row no-gutters>
          <!-- Step Navigation (Desktop) -->
          <v-col
            v-if="!isMobile"
            cols="3"
            class="bg-grey-lighten-4 pa-3 step-nav"
          >
            <v-list density="compact" nav class="bg-transparent">
              <v-list-item
                v-for="(step, index) in workflowSteps"
                :key="step.id"
                :active="index === currentStep"
                :disabled="!canNavigateToStep(index)"
                :class="getStepClass(index)"
                @click="navigateToStep(index)"
                rounded
              >
                <template v-slot:prepend>
                  <v-avatar
                    :color="getStepColor(index)"
                    size="32"
                    class="mr-2"
                  >
                    <v-icon
                      v-if="workflowStore.isStepCompleted(step.id)"
                      size="18"
                      color="white"
                    >
                      mdi-check
                    </v-icon>
                    <v-icon
                      v-else-if="workflowStore.isStepSkipped(step.id)"
                      size="18"
                      color="white"
                    >
                      mdi-skip-next
                    </v-icon>
                    <span v-else class="text-white text-body-2">{{ index + 1 }}</span>
                  </v-avatar>
                </template>
                <v-list-item-title class="text-body-2">
                  {{ step.title }}
                </v-list-item-title>
                <v-list-item-subtitle v-if="!step.required" class="text-caption">
                  Optional
                </v-list-item-subtitle>
              </v-list-item>
            </v-list>
          </v-col>

          <!-- Step Content -->
          <v-col :cols="isMobile ? 12 : 9" class="step-content">
            <!-- Mobile Step Indicator -->
            <div v-if="isMobile" class="pa-3 bg-grey-lighten-4">
              <div class="d-flex align-center">
                <v-avatar :color="getStepColor(currentStep)" size="40" class="mr-3">
                  <v-icon color="white">{{ currentStepData?.icon }}</v-icon>
                </v-avatar>
                <div>
                  <div class="text-subtitle-1 font-weight-medium">
                    {{ currentStepData?.title }}
                  </div>
                  <div class="text-caption text-grey">
                    {{ currentStepData?.required ? 'Required' : 'Optional' }}
                  </div>
                </div>
              </div>
            </div>

            <!-- Step Header (Desktop) -->
            <div v-if="!isMobile" class="pa-4 border-b">
              <div class="d-flex align-center">
                <v-avatar :color="getStepColor(currentStep)" size="48" class="mr-3">
                  <v-icon color="white" size="24">{{ currentStepData?.icon }}</v-icon>
                </v-avatar>
                <div>
                  <div class="text-h6">{{ currentStepData?.title }}</div>
                  <div class="text-body-2 text-grey">
                    {{ currentStepData?.description }}
                  </div>
                </div>
              </div>
            </div>

            <!-- Dynamic Step Component -->
            <div class="pa-4 step-body">
              <v-alert
                v-if="workflowStore.error"
                type="error"
                variant="tonal"
                closable
                class="mb-4"
                @click:close="workflowStore.error = null"
              >
                {{ workflowStore.error }}
              </v-alert>

              <!-- Shift Start Steps -->
              <template v-if="currentWorkflow === 'shift-start'">
                <WorkflowStepPreviousShift
                  v-if="currentStepData?.id === 'review-previous'"
                  @complete="onStepComplete"
                  @update="onStepUpdate"
                />
                <WorkflowStepAttendance
                  v-else-if="currentStepData?.id === 'confirm-attendance'"
                  @complete="onStepComplete"
                  @update="onStepUpdate"
                />
                <WorkflowStepTargets
                  v-else-if="currentStepData?.id === 'review-targets'"
                  @complete="onStepComplete"
                  @update="onStepUpdate"
                />
                <WorkflowStepEquipment
                  v-else-if="currentStepData?.id === 'check-equipment'"
                  @complete="onStepComplete"
                  @update="onStepUpdate"
                />
                <WorkflowStepStartShift
                  v-else-if="currentStepData?.id === 'start-shift'"
                  :workflow-data="workflowStore.workflowData"
                  @complete="onStepComplete"
                  @update="onStepUpdate"
                />
              </template>

              <!-- Shift End Steps -->
              <template v-else-if="currentWorkflow === 'shift-end'">
                <WorkflowStepCompleteness
                  v-if="currentStepData?.id === 'review-completeness'"
                  @complete="onStepComplete"
                  @update="onStepUpdate"
                />
                <WorkflowStepProduction
                  v-else-if="currentStepData?.id === 'complete-production'"
                  @complete="onStepComplete"
                  @update="onStepUpdate"
                />
                <WorkflowStepDowntime
                  v-else-if="currentStepData?.id === 'close-downtime'"
                  @complete="onStepComplete"
                  @update="onStepUpdate"
                />
                <WorkflowStepHandoff
                  v-else-if="currentStepData?.id === 'enter-handoff'"
                  @complete="onStepComplete"
                  @update="onStepUpdate"
                />
                <WorkflowStepSummary
                  v-else-if="currentStepData?.id === 'generate-summary'"
                  :workflow-data="workflowStore.workflowData"
                  @complete="onStepComplete"
                  @update="onStepUpdate"
                />
                <WorkflowStepEndShift
                  v-else-if="currentStepData?.id === 'end-shift'"
                  :workflow-data="workflowStore.workflowData"
                  @complete="onStepComplete"
                  @update="onStepUpdate"
                />
              </template>

              <!-- Fallback Loading -->
              <div v-else class="d-flex justify-center align-center pa-8">
                <v-progress-circular indeterminate color="primary" />
              </div>
            </div>
          </v-col>
        </v-row>
      </v-card-text>

      <!-- Actions -->
      <v-divider />
      <v-card-actions class="pa-4">
        <v-btn
          v-if="!workflowStore.isFirstStep"
          variant="outlined"
          @click="handlePrevious"
          prepend-icon="mdi-chevron-left"
        >
          Back
        </v-btn>

        <v-spacer />

        <v-btn
          v-if="workflowStore.canSkip"
          variant="text"
          color="grey"
          @click="handleSkip"
        >
          Skip
        </v-btn>

        <v-btn
          v-if="!workflowStore.isLastStep"
          color="primary"
          variant="elevated"
          :disabled="!workflowStore.canProceed"
          @click="handleNext"
          append-icon="mdi-chevron-right"
        >
          Next
        </v-btn>

        <v-btn
          v-else
          color="success"
          variant="elevated"
          :disabled="!workflowStore.canProceed"
          :loading="workflowStore.isLoading"
          @click="handleComplete"
          append-icon="mdi-check"
        >
          {{ currentWorkflow === 'shift-start' ? 'Start Shift' : 'End Shift' }}
        </v-btn>
      </v-card-actions>
    </v-card>

    <!-- Confirmation Dialog -->
    <v-dialog v-model="showCloseConfirm" max-width="400" persistent>
      <v-card>
        <v-card-title class="text-h6">Cancel Workflow?</v-card-title>
        <v-card-text>
          Are you sure you want to cancel this workflow? Your progress will be saved
          and you can resume later.
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="showCloseConfirm = false">
            Continue Workflow
          </v-btn>
          <v-btn color="error" variant="elevated" @click="confirmClose">
            Cancel Workflow
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useWorkflowStore } from '@/stores/workflowStore'
import { useResponsive } from '@/composables/useResponsive'

// Import step components
import WorkflowStepPreviousShift from './steps/WorkflowStepPreviousShift.vue'
import WorkflowStepAttendance from './steps/WorkflowStepAttendance.vue'
import WorkflowStepTargets from './steps/WorkflowStepTargets.vue'
import WorkflowStepEquipment from './steps/WorkflowStepEquipment.vue'
import WorkflowStepStartShift from './steps/WorkflowStepStartShift.vue'
import WorkflowStepCompleteness from './steps/WorkflowStepCompleteness.vue'
import WorkflowStepProduction from './steps/WorkflowStepProduction.vue'
import WorkflowStepDowntime from './steps/WorkflowStepDowntime.vue'
import WorkflowStepHandoff from './steps/WorkflowStepHandoff.vue'
import WorkflowStepSummary from './steps/WorkflowStepSummary.vue'
import WorkflowStepEndShift from './steps/WorkflowStepEndShift.vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue', 'complete', 'cancel'])

const workflowStore = useWorkflowStore()
const { isMobile } = useResponsive()

// State
const showCloseConfirm = ref(false)

// Computed
const isOpen = computed({
  get: () => props.modelValue && !!workflowStore.currentWorkflow,
  set: (value) => emit('update:modelValue', value)
})

const currentWorkflow = computed(() => workflowStore.currentWorkflow)
const currentStep = computed(() => workflowStore.currentStep)
const totalSteps = computed(() => workflowStore.totalSteps)
const workflowSteps = computed(() => workflowStore.workflowSteps)
const currentStepData = computed(() => workflowStore.currentStepData)

// Methods
const getStepColor = (index) => {
  const status = workflowStore.getStepStatus(index)
  switch (status) {
    case 'completed': return 'success'
    case 'skipped': return 'grey'
    case 'current': return 'primary'
    default: return 'grey-lighten-1'
  }
}

const getStepClass = (index) => {
  const status = workflowStore.getStepStatus(index)
  return {
    'step-completed': status === 'completed',
    'step-skipped': status === 'skipped',
    'step-current': status === 'current',
    'step-pending': status === 'pending'
  }
}

const canNavigateToStep = (index) => {
  if (index <= currentStep.value) return true
  const step = workflowSteps.value[index]
  return workflowStore.isStepCompleted(step?.id)
}

const navigateToStep = (index) => {
  if (canNavigateToStep(index)) {
    workflowStore.goToStep(index)
  }
}

const handlePrevious = () => {
  workflowStore.previousStep()
}

const handleNext = () => {
  workflowStore.nextStep()
}

const handleSkip = () => {
  workflowStore.skipStep()
}

const handleComplete = async () => {
  const result = await workflowStore.completeWorkflow()
  if (result.success) {
    emit('complete', result.data)
    emit('update:modelValue', false)
  }
}

const handleClose = () => {
  showCloseConfirm.value = true
}

const confirmClose = () => {
  showCloseConfirm.value = false
  workflowStore.cancelWorkflow()
  emit('cancel')
  emit('update:modelValue', false)
}

const onStepComplete = (data) => {
  if (currentStepData.value) {
    workflowStore.completeStep(currentStepData.value.id, data)
  }
}

const onStepUpdate = (data) => {
  if (currentStepData.value) {
    workflowStore.updateStepData(currentStepData.value.id, data)
  }
}

// Watch for workflow changes
watch(() => workflowStore.currentWorkflow, (newWorkflow) => {
  if (newWorkflow) {
    emit('update:modelValue', true)
  }
})
</script>

<style scoped>
.workflow-wizard {
  display: flex;
  flex-direction: column;
  max-height: 90vh;
}

.step-nav {
  border-right: 1px solid rgba(0, 0, 0, 0.12);
  max-height: calc(90vh - 180px);
  overflow-y: auto;
}

.step-content {
  display: flex;
  flex-direction: column;
  max-height: calc(90vh - 180px);
}

.step-body {
  flex: 1;
  overflow-y: auto;
  min-height: 300px;
}

.step-completed {
  opacity: 0.8;
}

.step-skipped {
  opacity: 0.6;
  text-decoration: line-through;
}

.step-pending {
  opacity: 0.5;
}

.border-b {
  border-bottom: 1px solid rgba(0, 0, 0, 0.12);
}

/* Mobile optimizations */
@media (max-width: 600px) {
  .workflow-wizard {
    max-height: 100vh;
  }

  .step-content {
    max-height: calc(100vh - 180px);
  }

  .step-body {
    min-height: 200px;
  }
}
</style>
