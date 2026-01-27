<template>
  <div class="alert-card" :class="[`severity-${alert.severity}`, `status-${alert.status}`]">
    <div class="alert-header">
      <div class="severity-badge" :class="alert.severity">
        {{ severityIcon }}
      </div>
      <div class="alert-title">
        <h4>{{ alert.title }}</h4>
        <span class="category">{{ categoryLabel }}</span>
      </div>
      <div class="alert-meta">
        <span class="timestamp" :title="alert.created_at">
          {{ timeAgo }}
        </span>
        <span v-if="alert.status !== 'active'" class="status-badge" :class="alert.status">
          {{ alert.status }}
        </span>
      </div>
    </div>

    <div class="alert-body">
      <p class="message">{{ alert.message }}</p>

      <div v-if="alert.recommendation" class="recommendation">
        <strong>Recommendation:</strong> {{ alert.recommendation }}
      </div>

      <div v-if="hasValues" class="values">
        <span v-if="alert.current_value !== null" class="value">
          Current: <strong>{{ formatValue(alert.current_value) }}</strong>
        </span>
        <span v-if="alert.threshold_value !== null" class="value">
          Threshold: <strong>{{ formatValue(alert.threshold_value) }}</strong>
        </span>
        <span v-if="alert.predicted_value !== null" class="value predicted">
          Predicted: <strong>{{ formatValue(alert.predicted_value) }}</strong>
          <span v-if="alert.confidence" class="confidence">
            ({{ alert.confidence }}% confidence)
          </span>
        </span>
      </div>
    </div>

    <div v-if="alert.status === 'active'" class="alert-actions">
      <button @click="$emit('acknowledge', alert.alert_id)" class="btn-acknowledge">
        Acknowledge
      </button>
      <button @click="$emit('resolve', alert)" class="btn-resolve">
        Resolve
      </button>
      <button @click="$emit('dismiss', alert.alert_id)" class="btn-dismiss">
        Dismiss
      </button>
    </div>

    <div v-else-if="alert.status === 'resolved'" class="resolved-info">
      <span>Resolved by {{ alert.resolved_by || 'System' }}</span>
      <span v-if="alert.resolution_notes" class="resolution-notes">
        {{ alert.resolution_notes }}
      </span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  alert: {
    type: Object,
    required: true
  }
})

defineEmits(['acknowledge', 'resolve', 'dismiss'])

const severityIcon = computed(() => {
  const icons = {
    urgent: '!',
    critical: '!',
    warning: '!',
    info: 'i'
  }
  return icons[props.alert.severity] || '?'
})

const categoryLabel = computed(() => {
  const labels = {
    otd: 'On-Time Delivery',
    quality: 'Quality',
    efficiency: 'Efficiency',
    capacity: 'Capacity',
    attendance: 'Attendance',
    downtime: 'Downtime',
    hold: 'Holds',
    trend: 'Trend'
  }
  return labels[props.alert.category] || props.alert.category
})

const hasValues = computed(() => {
  return props.alert.current_value !== null ||
         props.alert.threshold_value !== null ||
         props.alert.predicted_value !== null
})

const timeAgo = computed(() => {
  const created = new Date(props.alert.created_at)
  const now = new Date()
  const diffMs = now - created
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  return created.toLocaleDateString()
})

function formatValue(value) {
  if (value === null || value === undefined) return '-'
  const num = parseFloat(value)
  if (isNaN(num)) return value
  return num.toFixed(1)
}
</script>

<style scoped>
.alert-card {
  padding: 1rem;
  border-radius: 8px;
  border-left: 4px solid transparent;
  background: var(--color-surface);
  transition: box-shadow 0.2s;
}

.alert-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.alert-card.severity-urgent {
  border-left-color: #dc2626;
  background: rgba(220, 38, 38, 0.05);
}

.alert-card.severity-critical {
  border-left-color: #ea580c;
  background: rgba(234, 88, 12, 0.05);
}

.alert-card.severity-warning {
  border-left-color: #ca8a04;
  background: rgba(202, 138, 4, 0.05);
}

.alert-card.severity-info {
  border-left-color: #3b82f6;
  background: rgba(59, 130, 246, 0.05);
}

.alert-card.status-resolved,
.alert-card.status-dismissed {
  opacity: 0.7;
}

.alert-header {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

.severity-badge {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 0.9rem;
  flex-shrink: 0;
}

.severity-badge.urgent {
  background: #dc2626;
  color: white;
}

.severity-badge.critical {
  background: #ea580c;
  color: white;
}

.severity-badge.warning {
  background: #ca8a04;
  color: white;
}

.severity-badge.info {
  background: #3b82f6;
  color: white;
}

.alert-title {
  flex: 1;
}

.alert-title h4 {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 600;
  line-height: 1.3;
}

.category {
  font-size: 0.75rem;
  color: var(--color-text-muted);
}

.alert-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.25rem;
}

.timestamp {
  font-size: 0.75rem;
  color: var(--color-text-muted);
}

.status-badge {
  font-size: 0.65rem;
  padding: 0.15rem 0.4rem;
  border-radius: 3px;
  text-transform: uppercase;
}

.status-badge.acknowledged {
  background: #3b82f6;
  color: white;
}

.status-badge.resolved {
  background: #16a34a;
  color: white;
}

.status-badge.dismissed {
  background: #6b7280;
  color: white;
}

.alert-body {
  margin-bottom: 0.75rem;
}

.message {
  margin: 0 0 0.5rem;
  font-size: 0.875rem;
  white-space: pre-line;
}

.recommendation {
  font-size: 0.8rem;
  padding: 0.5rem;
  background: rgba(0, 0, 0, 0.05);
  border-radius: 4px;
  margin-bottom: 0.5rem;
}

.values {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  font-size: 0.8rem;
  color: var(--color-text-muted);
}

.value strong {
  color: var(--color-text);
}

.value.predicted {
  color: #7c3aed;
}

.confidence {
  font-size: 0.7rem;
  opacity: 0.8;
}

.alert-actions {
  display: flex;
  gap: 0.5rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--color-border);
}

.alert-actions button {
  padding: 0.4rem 0.75rem;
  font-size: 0.8rem;
  border-radius: 4px;
  cursor: pointer;
  border: 1px solid transparent;
}

.btn-acknowledge {
  background: #3b82f6;
  color: white;
}

.btn-resolve {
  background: #16a34a;
  color: white;
}

.btn-dismiss {
  background: transparent;
  border-color: var(--color-border);
  color: var(--color-text-muted);
}

.resolved-info {
  font-size: 0.8rem;
  color: var(--color-text-muted);
  padding-top: 0.5rem;
  border-top: 1px solid var(--color-border);
}

.resolution-notes {
  display: block;
  margin-top: 0.25rem;
  font-style: italic;
}
</style>
