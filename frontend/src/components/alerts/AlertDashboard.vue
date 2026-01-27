<template>
  <div class="alert-dashboard">
    <!-- Summary Header -->
    <div class="alert-summary-header">
      <div class="summary-stats">
        <div class="stat urgent" v-if="summary.urgent_count > 0">
          <span class="count">{{ summary.urgent_count }}</span>
          <span class="label">Urgent</span>
        </div>
        <div class="stat critical" v-if="summary.critical_count > 0">
          <span class="count">{{ summary.critical_count }}</span>
          <span class="label">Critical</span>
        </div>
        <div class="stat warning" v-if="summary.by_severity?.warning > 0">
          <span class="count">{{ summary.by_severity.warning }}</span>
          <span class="label">Warning</span>
        </div>
        <div class="stat info" v-if="summary.by_severity?.info > 0">
          <span class="count">{{ summary.by_severity.info }}</span>
          <span class="label">Info</span>
        </div>
        <div class="stat total">
          <span class="count">{{ summary.total_active }}</span>
          <span class="label">Total Active</span>
        </div>
      </div>
      <div class="actions">
        <button @click="generateAlerts" :disabled="generating" class="btn-generate">
          <span v-if="generating">Checking...</span>
          <span v-else>Check Now</span>
        </button>
      </div>
    </div>

    <!-- Filters -->
    <div class="alert-filters">
      <select v-model="filters.category" @change="loadAlerts">
        <option value="">All Categories</option>
        <option value="otd">On-Time Delivery</option>
        <option value="quality">Quality</option>
        <option value="efficiency">Efficiency</option>
        <option value="capacity">Capacity</option>
        <option value="attendance">Attendance</option>
        <option value="hold">Holds</option>
      </select>
      <select v-model="filters.severity" @change="loadAlerts">
        <option value="">All Severities</option>
        <option value="urgent">Urgent</option>
        <option value="critical">Critical</option>
        <option value="warning">Warning</option>
        <option value="info">Info</option>
      </select>
      <select v-model="filters.status" @change="loadAlerts">
        <option value="active">Active</option>
        <option value="acknowledged">Acknowledged</option>
        <option value="resolved">Resolved</option>
        <option value="">All</option>
      </select>
    </div>

    <!-- Urgent Alerts Section -->
    <div v-if="urgentAlerts.length > 0" class="alert-section urgent-section">
      <h3>Urgent Alerts</h3>
      <div class="alert-list">
        <AlertCard
          v-for="alert in urgentAlerts"
          :key="alert.alert_id"
          :alert="alert"
          @acknowledge="handleAcknowledge"
          @resolve="handleResolve"
          @dismiss="handleDismiss"
        />
      </div>
    </div>

    <!-- Critical Alerts Section -->
    <div v-if="criticalAlerts.length > 0" class="alert-section critical-section">
      <h3>Critical Alerts</h3>
      <div class="alert-list">
        <AlertCard
          v-for="alert in criticalAlerts"
          :key="alert.alert_id"
          :alert="alert"
          @acknowledge="handleAcknowledge"
          @resolve="handleResolve"
          @dismiss="handleDismiss"
        />
      </div>
    </div>

    <!-- All Alerts -->
    <div class="alert-section all-alerts">
      <h3>All Alerts ({{ alerts.length }})</h3>
      <div v-if="loading" class="loading">Loading alerts...</div>
      <div v-else-if="alerts.length === 0" class="no-alerts">
        No alerts matching your criteria
      </div>
      <div v-else class="alert-list">
        <AlertCard
          v-for="alert in alerts"
          :key="alert.alert_id"
          :alert="alert"
          @acknowledge="handleAcknowledge"
          @resolve="handleResolve"
          @dismiss="handleDismiss"
        />
      </div>
    </div>

    <!-- Resolve Dialog -->
    <div v-if="showResolveDialog" class="dialog-overlay" @click.self="closeResolveDialog">
      <div class="dialog">
        <h3>Resolve Alert</h3>
        <p>{{ resolvingAlert?.title }}</p>
        <textarea
          v-model="resolutionNotes"
          placeholder="Describe how the issue was resolved..."
          rows="4"
        ></textarea>
        <div class="dialog-actions">
          <button @click="closeResolveDialog" class="btn-cancel">Cancel</button>
          <button @click="confirmResolve" class="btn-resolve" :disabled="!resolutionNotes.trim()">
            Resolve
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import AlertCard from './AlertCard.vue'
import api from '@/services/api'

const alerts = ref([])
const summary = ref({
  total_active: 0,
  by_severity: {},
  by_category: {},
  critical_count: 0,
  urgent_count: 0
})
const loading = ref(false)
const generating = ref(false)

const filters = ref({
  category: '',
  severity: '',
  status: 'active'
})

const showResolveDialog = ref(false)
const resolvingAlert = ref(null)
const resolutionNotes = ref('')

const urgentAlerts = computed(() =>
  alerts.value.filter(a => a.severity === 'urgent' && a.status === 'active')
)

const criticalAlerts = computed(() =>
  alerts.value.filter(a => a.severity === 'critical' && a.status === 'active')
)

onMounted(() => {
  loadAlerts()
  loadSummary()
})

async function loadAlerts() {
  loading.value = true
  try {
    const params = new URLSearchParams()
    if (filters.value.category) params.append('category', filters.value.category)
    if (filters.value.severity) params.append('severity', filters.value.severity)
    if (filters.value.status) params.append('status', filters.value.status)

    const response = await api.get(`/alerts/?${params.toString()}`)
    alerts.value = response.data
  } catch (error) {
    console.error('Failed to load alerts:', error)
  } finally {
    loading.value = false
  }
}

async function loadSummary() {
  try {
    const response = await api.get('/alerts/summary')
    summary.value = response.data
  } catch (error) {
    console.error('Failed to load summary:', error)
  }
}

async function generateAlerts() {
  generating.value = true
  try {
    await api.post('/alerts/generate/check-all')
    await loadAlerts()
    await loadSummary()
  } catch (error) {
    console.error('Failed to generate alerts:', error)
  } finally {
    generating.value = false
  }
}

async function handleAcknowledge(alertId) {
  try {
    await api.post(`/alerts/${alertId}/acknowledge`, {})
    await loadAlerts()
    await loadSummary()
  } catch (error) {
    console.error('Failed to acknowledge alert:', error)
  }
}

function handleResolve(alert) {
  resolvingAlert.value = alert
  resolutionNotes.value = ''
  showResolveDialog.value = true
}

async function confirmResolve() {
  if (!resolvingAlert.value || !resolutionNotes.value.trim()) return

  try {
    await api.post(`/alerts/${resolvingAlert.value.alert_id}/resolve`, {
      resolution_notes: resolutionNotes.value
    })
    closeResolveDialog()
    await loadAlerts()
    await loadSummary()
  } catch (error) {
    console.error('Failed to resolve alert:', error)
  }
}

function closeResolveDialog() {
  showResolveDialog.value = false
  resolvingAlert.value = null
  resolutionNotes.value = ''
}

async function handleDismiss(alertId) {
  if (!confirm('Are you sure you want to dismiss this alert?')) return

  try {
    await api.post(`/alerts/${alertId}/dismiss`)
    await loadAlerts()
    await loadSummary()
  } catch (error) {
    console.error('Failed to dismiss alert:', error)
  }
}
</script>

<style scoped>
.alert-dashboard {
  padding: 1rem;
}

.alert-summary-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
  padding: 1rem;
  background: var(--color-surface);
  border-radius: 8px;
}

.summary-stats {
  display: flex;
  gap: 1.5rem;
}

.stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 0.5rem 1rem;
  border-radius: 8px;
}

.stat .count {
  font-size: 1.5rem;
  font-weight: bold;
}

.stat .label {
  font-size: 0.75rem;
  opacity: 0.8;
}

.stat.urgent {
  background: rgba(220, 38, 38, 0.1);
  color: #dc2626;
}

.stat.critical {
  background: rgba(234, 88, 12, 0.1);
  color: #ea580c;
}

.stat.warning {
  background: rgba(202, 138, 4, 0.1);
  color: #ca8a04;
}

.stat.info {
  background: rgba(59, 130, 246, 0.1);
  color: #3b82f6;
}

.stat.total {
  background: rgba(107, 114, 128, 0.1);
  color: #6b7280;
}

.btn-generate {
  padding: 0.5rem 1rem;
  background: var(--color-primary);
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.btn-generate:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.alert-filters {
  display: flex;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.alert-filters select {
  padding: 0.5rem;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  background: var(--color-surface);
}

.alert-section {
  margin-bottom: 2rem;
}

.alert-section h3 {
  margin-bottom: 1rem;
  font-size: 1.1rem;
  font-weight: 600;
}

.urgent-section h3 {
  color: #dc2626;
}

.critical-section h3 {
  color: #ea580c;
}

.alert-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.loading,
.no-alerts {
  padding: 2rem;
  text-align: center;
  color: var(--color-text-muted);
}

.dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.dialog {
  background: var(--color-surface);
  padding: 1.5rem;
  border-radius: 8px;
  width: 100%;
  max-width: 500px;
}

.dialog h3 {
  margin-bottom: 0.5rem;
}

.dialog p {
  margin-bottom: 1rem;
  color: var(--color-text-muted);
}

.dialog textarea {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  resize: vertical;
  margin-bottom: 1rem;
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
}

.btn-cancel {
  padding: 0.5rem 1rem;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  cursor: pointer;
}

.btn-resolve {
  padding: 0.5rem 1rem;
  background: #16a34a;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.btn-resolve:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
