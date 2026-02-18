<template>
  <div class="workflow-step-handoff">
    <!-- Handoff Notes Form -->
    <v-card variant="outlined" class="mb-4">
      <v-card-title class="bg-grey-lighten-4 py-2">
        <v-icon class="mr-2" size="20">mdi-note-text</v-icon>
        {{ $t('workflow.shiftHandoffNotes') }}
      </v-card-title>
      <v-card-text>
        <v-alert type="info" variant="tonal" density="compact" class="mb-4">
          {{ $t('workflow.handoffInfoAlert') }}
        </v-alert>

        <!-- Production Notes -->
        <v-textarea
          v-model="handoffNotes.production"
          :label="$t('workflow.productionNotes')"
          :placeholder="$t('workflow.productionNotesPlaceholder')"
          variant="outlined"
          rows="2"
          class="mb-3"
          @update:model-value="emitUpdate"
        />

        <!-- Quality Notes -->
        <v-textarea
          v-model="handoffNotes.quality"
          :label="$t('workflow.qualityNotes')"
          :placeholder="$t('workflow.qualityNotesPlaceholder')"
          variant="outlined"
          rows="2"
          class="mb-3"
          @update:model-value="emitUpdate"
        />

        <!-- Equipment Notes -->
        <v-textarea
          v-model="handoffNotes.equipment"
          :label="$t('workflow.equipmentNotes')"
          :placeholder="$t('workflow.equipmentNotesPlaceholder')"
          variant="outlined"
          rows="2"
          class="mb-3"
          @update:model-value="emitUpdate"
        />

        <!-- Personnel Notes -->
        <v-textarea
          v-model="handoffNotes.personnel"
          :label="$t('workflow.personnelNotes')"
          :placeholder="$t('workflow.personnelNotesPlaceholder')"
          variant="outlined"
          rows="2"
          class="mb-3"
          @update:model-value="emitUpdate"
        />

        <!-- Safety Notes -->
        <v-textarea
          v-model="handoffNotes.safety"
          :label="$t('workflow.safetyNotes')"
          :placeholder="$t('workflow.safetyNotesPlaceholder')"
          variant="outlined"
          rows="2"
          class="mb-3"
          @update:model-value="emitUpdate"
        />

        <!-- General Notes -->
        <v-textarea
          v-model="handoffNotes.general"
          :label="$t('workflow.additionalNotes')"
          :placeholder="$t('workflow.additionalNotesPlaceholder')"
          variant="outlined"
          rows="3"
          @update:model-value="emitUpdate"
        />
      </v-card-text>
    </v-card>

    <!-- Quick Add Common Issues -->
    <v-card variant="outlined" class="mb-4">
      <v-card-title class="bg-grey-lighten-4 py-2">
        <v-icon class="mr-2" size="20">mdi-lightning-bolt</v-icon>
        {{ $t('workflow.quickAddCommonNotes') }}
      </v-card-title>
      <v-card-text>
        <div class="d-flex flex-wrap gap-2">
          <v-chip
            v-for="note in commonNotes"
            :key="note.id"
            @click="addCommonNote(note)"
            variant="outlined"
            color="primary"
            class="cursor-pointer"
          >
            <v-icon start size="16">{{ note.icon }}</v-icon>
            {{ note.label }}
          </v-chip>
        </div>
      </v-card-text>
    </v-card>

    <!-- Priority Items -->
    <v-card variant="outlined" class="mb-4">
      <v-card-title class="d-flex align-center bg-grey-lighten-4 py-2">
        <v-icon class="mr-2" size="20">mdi-flag</v-icon>
        {{ $t('workflow.priorityItemsNextShift') }}
      </v-card-title>
      <v-card-text>
        <v-list density="compact">
          <v-list-item
            v-for="(item, index) in priorityItems"
            :key="index"
          >
            <template v-slot:prepend>
              <v-checkbox
                v-model="item.selected"
                hide-details
                density="compact"
                @update:model-value="emitUpdate"
              />
            </template>
            <v-list-item-title>{{ item.text }}</v-list-item-title>
          </v-list-item>
        </v-list>

        <!-- Add custom priority item -->
        <div class="d-flex align-center mt-2">
          <v-text-field
            v-model="newPriorityItem"
            density="compact"
            variant="outlined"
            :placeholder="$t('workflow.addCustomPriorityPlaceholder')"
            hide-details
            @keyup.enter="addPriorityItem"
          />
          <v-btn
            icon
            size="small"
            color="primary"
            class="ml-2"
            :disabled="!newPriorityItem.trim()"
            @click="addPriorityItem"
          >
            <v-icon>mdi-plus</v-icon>
          </v-btn>
        </div>
      </v-card-text>
    </v-card>

    <!-- Preview -->
    <v-expansion-panels class="mb-4">
      <v-expansion-panel>
        <v-expansion-panel-title>
          <v-icon class="mr-2">mdi-eye</v-icon>
          {{ $t('workflow.previewHandoffSummary') }}
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <div class="handoff-preview">
            <template v-for="(value, key) in handoffNotes" :key="key">
              <div v-if="value" class="mb-3">
                <div class="text-caption text-grey text-uppercase">{{ formatLabel(key) }}</div>
                <div class="text-body-2">{{ value }}</div>
              </div>
            </template>

            <div v-if="selectedPriorityItems.length > 0" class="mb-3">
              <div class="text-caption text-grey text-uppercase">{{ $t('workflow.priorityItems') }}</div>
              <ul class="text-body-2 pl-4">
                <li v-for="item in selectedPriorityItems" :key="item.text">{{ item.text }}</li>
              </ul>
            </div>

            <v-alert
              v-if="!hasContent"
              type="info"
              variant="tonal"
              density="compact"
            >
              {{ $t('workflow.noHandoffNotes') }}
            </v-alert>
          </div>
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>

    <!-- Confirmation -->
    <v-checkbox
      v-model="confirmed"
      :label="$t('workflow.handoffConfirmLabel')"
      color="primary"
      @update:model-value="handleConfirm"
    />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const emit = defineEmits(['complete', 'update'])

// State
const confirmed = ref(false)
const newPriorityItem = ref('')

const handoffNotes = ref({
  production: '',
  quality: '',
  equipment: '',
  personnel: '',
  safety: '',
  general: ''
})

const priorityItems = ref([
  { text: 'Follow up on WO-2024-002 quality hold', selected: false },
  { text: 'Check CNC Machine #2 sensor after PM', selected: false },
  { text: 'Expedite material delivery for Line 3', selected: false }
])

const commonNotes = [
  { id: 'behind', label: 'Behind schedule', icon: 'mdi-clock-alert', category: 'production', text: 'Production is behind schedule. Prioritize critical work orders.' },
  { id: 'quality-hold', label: 'Quality hold', icon: 'mdi-pause-circle', category: 'quality', text: 'Quality hold in progress. Awaiting disposition decision.' },
  { id: 'maintenance', label: 'Maintenance needed', icon: 'mdi-wrench', category: 'equipment', text: 'Equipment requires maintenance attention.' },
  { id: 'short-staff', label: 'Short staffed', icon: 'mdi-account-alert', category: 'personnel', text: 'Operating with reduced staff. May need coverage.' },
  { id: 'safety-incident', label: 'Safety incident', icon: 'mdi-alert-octagon', category: 'safety', text: 'Safety incident occurred. Report filed.' }
]

// Computed
const hasContent = computed(() => {
  return Object.values(handoffNotes.value).some(v => v.trim()) ||
         priorityItems.value.some(i => i.selected)
})

const selectedPriorityItems = computed(() => {
  return priorityItems.value.filter(i => i.selected)
})

// Methods
const formatLabel = (key) => {
  const labels = {
    production: t('workflow.productionNotes'),
    quality: t('workflow.qualityNotes'),
    equipment: t('workflow.equipmentNotes'),
    personnel: t('workflow.personnelNotes'),
    safety: t('workflow.safetyNotes'),
    general: t('workflow.additionalNotes')
  }
  return labels[key] || key
}

const addCommonNote = (note) => {
  const category = note.category
  if (handoffNotes.value[category]) {
    handoffNotes.value[category] += '\n' + note.text
  } else {
    handoffNotes.value[category] = note.text
  }
  emitUpdate()
}

const addPriorityItem = () => {
  if (newPriorityItem.value.trim()) {
    priorityItems.value.push({
      text: newPriorityItem.value.trim(),
      selected: true
    })
    newPriorityItem.value = ''
    emitUpdate()
  }
}

const emitUpdate = () => {
  emit('update', {
    handoffNotes: handoffNotes.value,
    priorityItems: selectedPriorityItems.value,
    isValid: confirmed.value
  })
}

const handleConfirm = (value) => {
  if (value) {
    emit('complete', {
      handoffNotes: handoffNotes.value,
      priorityItems: selectedPriorityItems.value
    })
  }
  emitUpdate()
}
</script>

<style scoped>
.gap-2 {
  gap: 8px;
}

.cursor-pointer {
  cursor: pointer;
}

.handoff-preview {
  background: #f5f5f5;
  border-radius: 8px;
  padding: 16px;
}

ul {
  margin: 0;
}
</style>
