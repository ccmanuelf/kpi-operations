<template>
  <v-dialog
    :model-value="modelValue"
    max-width="560"
    persistent
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon class="mr-2" color="primary">mdi-rocket-launch-outline</v-icon>
        {{ $t('onboarding.title') }}
        <v-spacer />
        <v-btn icon variant="text" size="small" @click="dismiss">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>

      <v-card-subtitle class="pb-0">
        {{ $t('onboarding.subtitle') }}
      </v-card-subtitle>

      <!-- Progress bar -->
      <v-card-text class="pb-2">
        <div class="d-flex align-center justify-space-between mb-1">
          <span class="text-body-2 text-medium-emphasis">
            {{ $t('onboarding.progress', { completed: completedCount, total: totalSteps }) }}
          </span>
          <span class="text-body-2 font-weight-medium">{{ progressPercent }}%</span>
        </div>
        <v-progress-linear
          :model-value="progressPercent"
          :color="allComplete ? 'success' : 'primary'"
          height="8"
          rounded
        />
      </v-card-text>

      <!-- All complete banner -->
      <v-card-text v-if="allComplete" class="pt-0 pb-2">
        <v-alert type="success" variant="tonal" density="compact">
          {{ $t('onboarding.allComplete') }}
        </v-alert>
      </v-card-text>

      <!-- Loading state -->
      <v-card-text v-if="loading" class="text-center py-8">
        <v-progress-circular indeterminate color="primary" />
      </v-card-text>

      <!-- Step list -->
      <v-list v-else lines="two" class="py-0">
        <v-list-item
          v-for="(step, index) in steps"
          :key="step.key"
          :class="{ 'bg-grey-lighten-4': step.completed }"
        >
          <template #prepend>
            <v-avatar :color="step.completed ? 'success' : 'grey-lighten-2'" size="36">
              <v-icon :color="step.completed ? 'white' : step.color" size="20">
                {{ step.completed ? 'mdi-check' : step.icon }}
              </v-icon>
            </v-avatar>
          </template>

          <v-list-item-title :class="{ 'text-decoration-line-through text-medium-emphasis': step.completed }">
            {{ index + 1 }}. {{ step.title }}
          </v-list-item-title>
          <v-list-item-subtitle>
            {{ step.description }}
          </v-list-item-subtitle>

          <template #append>
            <v-chip
              v-if="step.completed"
              color="success"
              variant="tonal"
              size="small"
              label
            >
              {{ $t('onboarding.completed') }}
            </v-chip>
            <v-btn
              v-else
              color="primary"
              variant="tonal"
              size="small"
              :to="step.route"
              @click="dismiss"
            >
              {{ $t('onboarding.goTo') }}
            </v-btn>
          </template>
        </v-list-item>
      </v-list>

      <v-divider />

      <!-- Actions -->
      <v-card-actions>
        <v-btn
          variant="text"
          size="small"
          prepend-icon="mdi-refresh"
          :loading="loading"
          @click="$emit('refresh')"
        >
          {{ $t('onboarding.refresh') }}
        </v-btn>
        <v-spacer />
        <v-btn color="primary" variant="text" @click="dismiss">
          {{ $t('onboarding.dismiss') }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
defineProps({
  /** Controls dialog visibility (v-model). */
  modelValue: {
    type: Boolean,
    default: false,
  },
  /** Whether the status is currently loading. */
  loading: {
    type: Boolean,
    default: false,
  },
  /** Enriched step list from useOnboarding composable. */
  steps: {
    type: Array,
    default: () => [],
  },
  /** Number of completed steps. */
  completedCount: {
    type: Number,
    default: 0,
  },
  /** Total number of steps. */
  totalSteps: {
    type: Number,
    default: 5,
  },
  /** Whether all steps are complete. */
  allComplete: {
    type: Boolean,
    default: false,
  },
  /** Progress percentage (0-100). */
  progressPercent: {
    type: Number,
    default: 0,
  },
})

const emit = defineEmits(['update:modelValue', 'refresh'])

function dismiss() {
  emit('update:modelValue', false)
}
</script>
