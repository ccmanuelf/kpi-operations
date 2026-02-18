<template>
  <!-- Quick Production Dialog -->
  <v-dialog v-model="showProductionDialog" max-width="400" persistent>
    <v-card>
      <v-card-title class="bg-primary text-white d-flex align-center">
        <v-icon class="mr-2">mdi-package-variant-plus</v-icon>
        {{ t('production.title') }}
      </v-card-title>
      <v-card-text class="pa-4">
        <v-select
          v-model="productionForm.workOrderId"
          :items="workOrderOptions"
          item-title="text"
          item-value="value"
          :label="t('production.workOrder')"
          variant="outlined"
          class="mb-3"
        />
        <v-text-field
          v-model.number="productionForm.quantity"
          :label="t('production.unitsProduced')"
          type="number"
          variant="outlined"
          min="1"
          :rules="[v => v > 0 || t('common.required')]"
        />
        <div class="d-flex gap-2 justify-center mt-2">
          <v-btn
            v-for="preset in productionPresets"
            :key="preset"
            variant="outlined"
            size="small"
            @click="productionForm.quantity = preset"
          >
            {{ preset }}
          </v-btn>
        </div>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="showProductionDialog = false">{{ t('common.cancel') }}</v-btn>
        <v-btn
          color="primary"
          variant="elevated"
          :loading="isSubmitting"
          :disabled="!productionForm.workOrderId || !productionForm.quantity"
          @click="$emit('submitProduction')"
        >
          {{ t('common.submit') }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- Downtime Dialog -->
  <v-dialog v-model="showDowntimeDialog" max-width="450" persistent>
    <v-card>
      <v-card-title class="bg-warning text-white d-flex align-center">
        <v-icon class="mr-2">mdi-clock-alert</v-icon>
        {{ t('downtime.title') }}
      </v-card-title>
      <v-card-text class="pa-4">
        <v-select
          v-model="downtimeForm.workOrderId"
          :items="workOrderOptions"
          item-title="text"
          item-value="value"
          :label="t('production.workOrder')"
          variant="outlined"
          class="mb-3"
        />
        <v-select
          v-model="downtimeForm.reason"
          :items="downtimeReasons"
          :label="t('downtime.reason')"
          variant="outlined"
          class="mb-3"
        />
        <v-text-field
          v-model.number="downtimeForm.minutes"
          :label="t('downtime.duration')"
          type="number"
          variant="outlined"
          min="1"
        />
        <v-textarea
          v-model="downtimeForm.notes"
          :label="t('production.notes')"
          variant="outlined"
          rows="2"
          class="mt-3"
        />
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="showDowntimeDialog = false">{{ t('common.cancel') }}</v-btn>
        <v-btn
          color="warning"
          variant="elevated"
          :loading="isSubmitting"
          :disabled="!downtimeForm.workOrderId || !downtimeForm.reason"
          @click="$emit('submitDowntime')"
        >
          {{ t('common.submit') }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- Quality Check Dialog -->
  <v-dialog v-model="showQualityDialog" max-width="450" persistent>
    <v-card>
      <v-card-title class="bg-success text-white d-flex align-center">
        <v-icon class="mr-2">mdi-check-decagram</v-icon>
        {{ t('quality.title') }}
      </v-card-title>
      <v-card-text class="pa-4">
        <v-select
          v-model="qualityForm.workOrderId"
          :items="workOrderOptions"
          item-title="text"
          item-value="value"
          :label="t('production.workOrder')"
          variant="outlined"
          class="mb-3"
        />
        <v-text-field
          v-model.number="qualityForm.inspectedQty"
          :label="t('quality.inspectedQty')"
          type="number"
          variant="outlined"
          min="1"
          class="mb-3"
        />
        <v-text-field
          v-model.number="qualityForm.defectQty"
          :label="t('quality.defectQty')"
          type="number"
          variant="outlined"
          min="0"
        />
        <v-select
          v-if="qualityForm.defectQty > 0"
          v-model="qualityForm.defectType"
          :items="defectTypes"
          :label="t('quality.defectType')"
          variant="outlined"
          class="mt-3"
        />
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="showQualityDialog = false">{{ t('common.cancel') }}</v-btn>
        <v-btn
          color="success"
          variant="elevated"
          :loading="isSubmitting"
          :disabled="!qualityForm.workOrderId || !qualityForm.inspectedQty"
          @click="$emit('submitQuality')"
        >
          {{ t('common.submit') }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- Request Help Dialog -->
  <v-dialog v-model="showHelpDialog" max-width="400" persistent>
    <v-card>
      <v-card-title class="bg-error text-white d-flex align-center">
        <v-icon class="mr-2">mdi-hand-wave</v-icon>
        {{ t('common.help') }}
      </v-card-title>
      <v-card-text class="pa-4">
        <v-select
          v-model="helpForm.type"
          :items="helpTypes"
          :label="t('common.select')"
          variant="outlined"
          class="mb-3"
        />
        <v-textarea
          v-model="helpForm.description"
          :label="t('common.details')"
          variant="outlined"
          rows="3"
        />
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="showHelpDialog = false">{{ t('common.cancel') }}</v-btn>
        <v-btn
          color="error"
          variant="elevated"
          :loading="isSubmitting"
          :disabled="!helpForm.type || !helpForm.description"
          @click="$emit('submitHelpRequest')"
        >
          {{ t('common.submit') }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

defineProps({
  isSubmitting: Boolean,
  productionForm: Object,
  downtimeForm: Object,
  qualityForm: Object,
  helpForm: Object,
  workOrderOptions: Array,
  productionPresets: Array,
  downtimeReasons: Array,
  defectTypes: Array,
  helpTypes: Array
})

const showProductionDialog = defineModel('showProductionDialog', { type: Boolean })
const showDowntimeDialog = defineModel('showDowntimeDialog', { type: Boolean })
const showQualityDialog = defineModel('showQualityDialog', { type: Boolean })
const showHelpDialog = defineModel('showHelpDialog', { type: Boolean })

defineEmits([
  'submitProduction',
  'submitDowntime',
  'submitQuality',
  'submitHelpRequest'
])
</script>
