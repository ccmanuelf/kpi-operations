<template>
  <div class="table-skeleton" :aria-busy="true" aria-label="Loading table data">
    <!-- Header Skeleton -->
    <div class="table-skeleton__header" v-if="showHeader">
      <div class="table-skeleton__header-row">
        <div
          v-for="col in columns"
          :key="`header-${col}`"
          class="table-skeleton__header-cell"
          :style="{ width: getColumnWidth(col) }"
        >
          <div class="skeleton-pulse skeleton-text skeleton-text--header"></div>
        </div>
      </div>
    </div>

    <!-- Body Skeleton -->
    <div class="table-skeleton__body">
      <div
        v-for="row in rows"
        :key="`row-${row}`"
        class="table-skeleton__row"
        :style="{ animationDelay: `${row * 50}ms` }"
      >
        <div
          v-for="col in columns"
          :key="`cell-${row}-${col}`"
          class="table-skeleton__cell"
          :style="{ width: getColumnWidth(col) }"
        >
          <div
            class="skeleton-pulse skeleton-text"
            :class="{ 'skeleton-text--short': col % 3 === 0 }"
          ></div>
        </div>
      </div>
    </div>

    <!-- Pagination Skeleton -->
    <div class="table-skeleton__footer" v-if="showPagination">
      <div class="skeleton-pulse skeleton-text skeleton-text--short"></div>
      <div class="table-skeleton__pagination">
        <div class="skeleton-pulse skeleton-circle"></div>
        <div class="skeleton-pulse skeleton-circle"></div>
        <div class="skeleton-pulse skeleton-circle"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * TableSkeleton - Animated loading placeholder for data tables.
 *
 * Renders a pulsing skeleton UI that mimics a table structure with header,
 * body rows, and optional pagination footer. Used as a loading state while
 * table data is being fetched. Supports reduced-motion and dark theme.
 *
 * @prop {number} rows - Number of skeleton body rows (default: 5)
 * @prop {number} columns - Number of skeleton columns (default: 6)
 * @prop {boolean} showHeader - Whether to render the header skeleton (default: true)
 * @prop {boolean} showPagination - Whether to render the footer skeleton (default: true)
 * @prop {Array} columnWidths - Optional custom column width percentages
 */
defineProps({
  rows: {
    type: Number,
    default: 5
  },
  columns: {
    type: Number,
    default: 6
  },
  showHeader: {
    type: Boolean,
    default: true
  },
  showPagination: {
    type: Boolean,
    default: true
  },
  columnWidths: {
    type: Array,
    default: () => []
  }
})

const getColumnWidth = (colIndex) => {
  // Default varying widths if not specified
  const defaultWidths = ['15%', '20%', '15%', '15%', '20%', '15%']
  return defaultWidths[colIndex % defaultWidths.length]
}
</script>

<style scoped>
.table-skeleton {
  background: var(--cds-layer-02);
  border: 1px solid var(--cds-border-subtle-00);
  border-radius: var(--cds-border-radius-md);
  overflow: hidden;
}

.table-skeleton__header {
  background: var(--cds-layer-01);
  border-bottom: 1px solid var(--cds-border-subtle-01);
}

.table-skeleton__header-row,
.table-skeleton__row {
  display: flex;
  align-items: center;
  padding: var(--cds-spacing-04) var(--cds-spacing-05);
}

.table-skeleton__header-cell,
.table-skeleton__cell {
  padding: 0 var(--cds-spacing-03);
}

.table-skeleton__row {
  border-bottom: 1px solid var(--cds-border-subtle-00);
  animation: rowFadeIn var(--cds-duration-moderate-02) var(--cds-easing-entrance-productive) backwards;
}

.table-skeleton__row:last-child {
  border-bottom: none;
}

.table-skeleton__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--cds-spacing-04) var(--cds-spacing-05);
  background: var(--cds-layer-01);
  border-top: 1px solid var(--cds-border-subtle-00);
}

.table-skeleton__pagination {
  display: flex;
  gap: var(--cds-spacing-02);
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

.skeleton-text--header {
  height: 14px;
  width: 80%;
}

.skeleton-text--short {
  width: 60%;
}

.skeleton-circle {
  width: 32px;
  height: 32px;
  border-radius: 50%;
}

@keyframes pulse {
  0%, 100% {
    background-position: 200% 0;
  }
  50% {
    background-position: -200% 0;
  }
}

@keyframes rowFadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
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

/* Reduced motion support */
@media (prefers-reduced-motion: reduce) {
  .skeleton-pulse {
    animation: none;
    background: var(--cds-gray-20);
  }

  .table-skeleton__row {
    animation: none;
  }
}
</style>
