<template>
  <v-dialog
    :model-value="modelValue"
    max-width="700"
    persistent
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <v-card>
      <v-card-title class="d-flex align-center bg-success text-white">
        <v-icon start>mdi-check-decagram</v-icon>
        {{ t('capacityPlanning.scheduleCommit.title') }}
        <v-spacer />
        <v-btn
          icon="mdi-close"
          variant="text"
          size="small"
          @click="$emit('close')"
        />
      </v-card-title>
      <v-card-text class="pa-4">
        <!-- Schedule Summary -->
        <v-card v-if="schedule" variant="outlined" class="mb-4">
          <v-card-text>
            <v-row>
              <v-col cols="4">
                <div class="text-caption text-grey">{{ t('capacityPlanning.scheduleCommit.schedule') }}</div>
                <div class="text-subtitle-1 font-weight-bold">{{ schedule.name }}</div>
              </v-col>
              <v-col cols="4">
                <div class="text-caption text-grey">{{ t('common.period') }}</div>
                <div class="text-subtitle-1">
                  {{ formatDate(schedule.start_date) }} - {{ formatDate(schedule.end_date) }}
                </div>
              </v-col>
              <v-col cols="4">
                <div class="text-caption text-grey">{{ t('capacityPlanning.scheduleCommit.orders') }}</div>
                <div class="text-subtitle-1">{{ schedule.order_count || 0 }}</div>
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>

        <!-- Warning -->
        <v-alert type="warning" variant="tonal" class="mb-4">
          <strong>{{ t('capacityPlanning.scheduleCommit.warningTitle') }}</strong>
          {{ t('capacityPlanning.scheduleCommit.warningBody') }}
        </v-alert>

        <!-- KPI Commitments -->
        <div class="text-subtitle-1 font-weight-bold mb-3">{{ t('capacityPlanning.scheduleCommit.kpiCommitments') }}</div>
        <p class="text-body-2 text-grey mb-3">
          {{ t('capacityPlanning.scheduleCommit.kpiDescription') }}
        </p>

        <v-row v-for="(kpi, index) in kpiCommitments" :key="index" dense class="mb-2">
          <v-col cols="5">
            <v-text-field
              v-model="kpi.name"
              :label="t('kpi.name')"
              variant="outlined"
              density="compact"
              :readonly="kpi.readonly"
            />
          </v-col>
          <v-col cols="3">
            <v-text-field
              v-model.number="kpi.target"
              :label="t('common.target')"
              type="number"
              variant="outlined"
              density="compact"
            />
          </v-col>
          <v-col cols="3">
            <v-text-field
              v-model="kpi.unit"
              :label="t('common.unit')"
              variant="outlined"
              density="compact"
            />
          </v-col>
          <v-col cols="1" class="d-flex align-center">
            <v-btn
              v-if="!kpi.readonly"
              icon="mdi-delete"
              size="x-small"
              variant="text"
              color="error"
              @click="removeKPI(index)"
            />
          </v-col>
        </v-row>

        <v-btn
          color="primary"
          variant="text"
          size="small"
          class="mt-2"
          @click="addKPI"
        >
          <v-icon start>mdi-plus</v-icon>
          {{ t('capacityPlanning.scheduleCommit.addKpi') }}
        </v-btn>

        <!-- Notes -->
        <v-textarea
          v-model="commitNotes"
          :label="t('capacityPlanning.scheduleCommit.commitNotes')"
          variant="outlined"
          rows="3"
          class="mt-4"
          :placeholder="t('capacityPlanning.scheduleCommit.commitNotesPlaceholder')"
        />
      </v-card-text>
      <v-card-actions>
        <v-btn variant="text" @click="$emit('close')">{{ t('common.cancel') }}</v-btn>
        <v-spacer />
        <v-btn
          color="success"
          variant="elevated"
          :loading="isCommitting"
          @click="commitSchedule"
        >
          <v-icon start>mdi-check</v-icon>
          {{ t('capacityPlanning.scheduleCommit.commitSchedule') }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, reactive, watch } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  schedule: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['update:modelValue', 'close', 'commit'])

const isCommitting = ref(false)
const commitNotes = ref('')

// Default KPI commitments
const kpiCommitments = reactive([
  { name: t('capacityPlanning.scheduleCommit.defaultKpi.onTimeDelivery'), target: 95, unit: '%', readonly: true },
  { name: t('capacityPlanning.scheduleCommit.defaultKpi.productionEfficiency'), target: 85, unit: '%', readonly: true },
  { name: t('capacityPlanning.scheduleCommit.defaultKpi.qualityFpy'), target: 98, unit: '%', readonly: true },
  { name: t('capacityPlanning.scheduleCommit.defaultKpi.capacityUtilization'), target: 80, unit: '%', readonly: true }
])

const formatDate = (date) => {
  if (!date) return ''
  return new Date(date).toLocaleDateString()
}

const addKPI = () => {
  kpiCommitments.push({
    name: '',
    target: 0,
    unit: '',
    readonly: false
  })
}

const removeKPI = (index) => {
  kpiCommitments.splice(index, 1)
}

const commitSchedule = async () => {
  isCommitting.value = true

  const commitments = kpiCommitments.map(kpi => ({
    kpi_name: kpi.name,
    target_value: kpi.target,
    unit: kpi.unit,
    period_start: props.schedule?.start_date,
    period_end: props.schedule?.end_date,
    notes: commitNotes.value
  }))

  emit('commit', commitments)
  isCommitting.value = false
}

// Reset form when dialog opens
watch(() => props.modelValue, (newVal) => {
  if (newVal) {
    commitNotes.value = ''
  }
})
</script>
