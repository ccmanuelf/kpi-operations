<template>
  <v-card
    class="card-skeleton"
    :class="[`card-skeleton--${variant}`]"
    :aria-busy="true"
    aria-label="Loading content"
  >
    <v-card-text :class="{ 'pa-4': true }">
      <!-- KPI Card Skeleton -->
      <template v-if="variant === 'kpi'">
        <div class="d-flex align-center justify-space-between mb-3">
          <div class="skeleton-pulse skeleton-text skeleton-text--label" style="width: 40%"></div>
          <div class="skeleton-pulse skeleton-circle skeleton-circle--sm"></div>
        </div>
        <div class="skeleton-pulse skeleton-text skeleton-text--value mb-2"></div>
        <div class="skeleton-pulse skeleton-bar"></div>
        <div class="d-flex justify-space-between mt-3">
          <div class="skeleton-pulse skeleton-text skeleton-text--small" style="width: 30%"></div>
          <div class="skeleton-pulse skeleton-text skeleton-text--small" style="width: 20%"></div>
        </div>
      </template>

      <!-- Stats Card Skeleton -->
      <template v-else-if="variant === 'stats'">
        <div class="skeleton-pulse skeleton-text skeleton-text--label mb-2" style="width: 50%"></div>
        <div class="skeleton-pulse skeleton-text skeleton-text--value"></div>
      </template>

      <!-- Chart Card Skeleton -->
      <template v-else-if="variant === 'chart'">
        <div class="d-flex align-center justify-space-between mb-4">
          <div class="skeleton-pulse skeleton-text skeleton-text--title" style="width: 40%"></div>
          <div class="d-flex gap-2">
            <div class="skeleton-pulse skeleton-button"></div>
            <div class="skeleton-pulse skeleton-button"></div>
          </div>
        </div>
        <div class="skeleton-chart">
          <div class="skeleton-chart__y-axis">
            <div v-for="i in 5" :key="i" class="skeleton-pulse skeleton-text skeleton-text--small"></div>
          </div>
          <div class="skeleton-chart__area">
            <svg viewBox="0 0 400 150" preserveAspectRatio="none" class="skeleton-chart__line">
              <path
                d="M0,120 C50,100 100,80 150,90 C200,100 250,60 300,70 C350,80 380,50 400,40"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
              />
            </svg>
          </div>
        </div>
      </template>

      <!-- Form Card Skeleton -->
      <template v-else-if="variant === 'form'">
        <div class="skeleton-pulse skeleton-text skeleton-text--title mb-4" style="width: 30%"></div>
        <div v-for="i in fields" :key="i" class="mb-4">
          <div class="skeleton-pulse skeleton-text skeleton-text--label mb-2" style="width: 25%"></div>
          <div class="skeleton-pulse skeleton-input"></div>
        </div>
        <div class="d-flex justify-end gap-2 mt-4">
          <div class="skeleton-pulse skeleton-button"></div>
          <div class="skeleton-pulse skeleton-button skeleton-button--primary"></div>
        </div>
      </template>

      <!-- Default Card Skeleton -->
      <template v-else>
        <div class="skeleton-pulse skeleton-text skeleton-text--title mb-3" style="width: 60%"></div>
        <div class="skeleton-pulse skeleton-text mb-2"></div>
        <div class="skeleton-pulse skeleton-text mb-2" style="width: 90%"></div>
        <div class="skeleton-pulse skeleton-text" style="width: 70%"></div>
      </template>
    </v-card-text>
  </v-card>
</template>

<script setup>
defineProps({
  variant: {
    type: String,
    default: 'default',
    validator: (v) => ['default', 'kpi', 'stats', 'chart', 'form'].includes(v)
  },
  fields: {
    type: Number,
    default: 3
  }
})
</script>

<style scoped>
.card-skeleton {
  overflow: hidden;
}

/* Skeleton elements */
.skeleton-pulse {
  background: linear-gradient(
    90deg,
    var(--cds-gray-20) 0%,
    var(--cds-gray-10) 50%,
    var(--cds-gray-20) 100%
  );
  background-size: 200% 100%;
  animation: pulse 1.5s ease-in-out infinite;
  border-radius: var(--cds-border-radius-sm);
}

.skeleton-text {
  height: 16px;
  width: 100%;
}

.skeleton-text--label {
  height: 12px;
}

.skeleton-text--title {
  height: 20px;
}

.skeleton-text--value {
  height: 32px;
  width: 50%;
}

.skeleton-text--small {
  height: 12px;
}

.skeleton-circle {
  width: 40px;
  height: 40px;
  border-radius: 50%;
}

.skeleton-circle--sm {
  width: 24px;
  height: 24px;
}

.skeleton-bar {
  height: 8px;
  width: 100%;
  border-radius: 4px;
}

.skeleton-input {
  height: 40px;
  width: 100%;
  border-radius: var(--cds-border-radius-md);
}

.skeleton-button {
  height: 36px;
  width: 80px;
  border-radius: var(--cds-border-radius-md);
}

.skeleton-button--primary {
  width: 100px;
}

/* Chart skeleton */
.skeleton-chart {
  display: flex;
  height: 150px;
  margin-top: var(--cds-spacing-04);
}

.skeleton-chart__y-axis {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  width: 40px;
  padding-right: var(--cds-spacing-03);
}

.skeleton-chart__y-axis .skeleton-text--small {
  width: 30px;
}

.skeleton-chart__area {
  flex: 1;
  position: relative;
  border-left: 1px solid var(--cds-border-subtle-00);
  border-bottom: 1px solid var(--cds-border-subtle-00);
}

.skeleton-chart__line {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  color: var(--cds-gray-30);
  animation: chartPulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% {
    background-position: 200% 0;
  }
  50% {
    background-position: -200% 0;
  }
}

@keyframes chartPulse {
  0%, 100% {
    opacity: 0.3;
  }
  50% {
    opacity: 0.6;
  }
}

/* Dark theme support */
[data-theme="dark"] .skeleton-pulse,
.dark-theme .skeleton-pulse {
  background: linear-gradient(
    90deg,
    var(--cds-gray-70) 0%,
    var(--cds-gray-80) 50%,
    var(--cds-gray-70) 100%
  );
  background-size: 200% 100%;
}

[data-theme="dark"] .skeleton-chart__line,
.dark-theme .skeleton-chart__line {
  color: var(--cds-gray-60);
}

/* Reduced motion support */
@media (prefers-reduced-motion: reduce) {
  .skeleton-pulse,
  .skeleton-chart__line {
    animation: none;
  }

  .skeleton-pulse {
    background: var(--cds-gray-20);
  }
}
</style>
