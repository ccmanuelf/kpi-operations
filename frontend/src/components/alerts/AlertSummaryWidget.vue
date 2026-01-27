<template>
  <div class="alert-summary-widget" :class="{ 'has-urgent': summary.urgent_count > 0 }">
    <div class="widget-header">
      <h3>
        <span class="icon">!</span>
        Alerts
      </h3>
      <router-link to="/alerts" class="view-all">View All</router-link>
    </div>

    <div v-if="loading" class="loading">Loading...</div>

    <div v-else-if="summary.total_active === 0" class="no-alerts">
      <span class="check-icon">OK</span>
      <span>No active alerts</span>
    </div>

    <div v-else class="alert-counts">
      <div v-if="summary.urgent_count > 0" class="count urgent">
        <span class="number">{{ summary.urgent_count }}</span>
        <span class="label">Urgent</span>
      </div>
      <div v-if="summary.critical_count > 0" class="count critical">
        <span class="number">{{ summary.critical_count }}</span>
        <span class="label">Critical</span>
      </div>
      <div v-if="summary.by_severity?.warning > 0" class="count warning">
        <span class="number">{{ summary.by_severity.warning }}</span>
        <span class="label">Warning</span>
      </div>
      <div v-if="summary.by_severity?.info > 0" class="count info">
        <span class="number">{{ summary.by_severity.info }}</span>
        <span class="label">Info</span>
      </div>
    </div>

    <!-- Category breakdown -->
    <div v-if="summary.total_active > 0" class="category-breakdown">
      <div v-for="(count, category) in summary.by_category" :key="category" class="category-item">
        <span class="category-label">{{ formatCategory(category) }}</span>
        <span class="category-count">{{ count }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import api from '@/services/api'

const summary = ref({
  total_active: 0,
  by_severity: {},
  by_category: {},
  critical_count: 0,
  urgent_count: 0
})
const loading = ref(true)
let refreshInterval = null

onMounted(() => {
  loadSummary()
  // Refresh every 5 minutes
  refreshInterval = setInterval(loadSummary, 5 * 60 * 1000)
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
})

async function loadSummary() {
  try {
    const response = await api.get('/alerts/summary')
    summary.value = response.data
  } catch (error) {
    console.error('Failed to load alert summary:', error)
  } finally {
    loading.value = false
  }
}

function formatCategory(category) {
  const labels = {
    otd: 'OTD',
    quality: 'Quality',
    efficiency: 'Efficiency',
    capacity: 'Capacity',
    attendance: 'Attendance',
    downtime: 'Downtime',
    hold: 'Holds',
    trend: 'Trends'
  }
  return labels[category] || category
}
</script>

<style scoped>
.alert-summary-widget {
  padding: 1rem;
  background: var(--color-surface);
  border-radius: 8px;
  border: 1px solid var(--color-border);
}

.alert-summary-widget.has-urgent {
  border-color: #dc2626;
  animation: pulse-border 2s infinite;
}

@keyframes pulse-border {
  0%, 100% { border-color: #dc2626; }
  50% { border-color: rgba(220, 38, 38, 0.3); }
}

.widget-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.widget-header h3 {
  margin: 0;
  font-size: 1rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.icon {
  width: 20px;
  height: 20px;
  background: var(--color-primary);
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  font-weight: bold;
}

.view-all {
  font-size: 0.8rem;
  color: var(--color-primary);
  text-decoration: none;
}

.view-all:hover {
  text-decoration: underline;
}

.loading {
  text-align: center;
  padding: 1rem;
  color: var(--color-text-muted);
}

.no-alerts {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 1rem;
  color: #16a34a;
}

.check-icon {
  font-size: 0.9rem;
  font-weight: bold;
}

.alert-counts {
  display: flex;
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.count {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 0.5rem;
  border-radius: 6px;
}

.count .number {
  font-size: 1.5rem;
  font-weight: bold;
}

.count .label {
  font-size: 0.65rem;
  text-transform: uppercase;
  opacity: 0.8;
}

.count.urgent {
  background: rgba(220, 38, 38, 0.1);
  color: #dc2626;
}

.count.critical {
  background: rgba(234, 88, 12, 0.1);
  color: #ea580c;
}

.count.warning {
  background: rgba(202, 138, 4, 0.1);
  color: #ca8a04;
}

.count.info {
  background: rgba(59, 130, 246, 0.1);
  color: #3b82f6;
}

.category-breakdown {
  border-top: 1px solid var(--color-border);
  padding-top: 0.75rem;
}

.category-item {
  display: flex;
  justify-content: space-between;
  font-size: 0.8rem;
  padding: 0.25rem 0;
}

.category-label {
  color: var(--color-text-muted);
}

.category-count {
  font-weight: 500;
}
</style>
