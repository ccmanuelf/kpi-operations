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
        <button @click="showGuide = true" class="btn-help">
          <span>How to Use</span>
        </button>
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

    <!-- How-to Guide Dialog -->
    <div v-if="showGuide" class="dialog-overlay" @click.self="showGuide = false">
      <div class="dialog guide-dialog">
        <div class="guide-header">
          <h3>📚 How to Use Intelligent Alerts</h3>
          <button @click="showGuide = false" class="btn-close">×</button>
        </div>

        <div class="guide-tabs">
          <button
            v-for="tab in guideTabs"
            :key="tab.id"
            :class="['tab-btn', { active: activeGuideTab === tab.id }]"
            @click="activeGuideTab = tab.id"
          >
            {{ tab.label }}
          </button>
        </div>

        <div class="guide-content">
          <!-- Quick Start Tab -->
          <div v-if="activeGuideTab === 'quickstart'" class="tab-content">
            <div class="info-box">
              <strong>Welcome to Intelligent Alerts!</strong>
              <p>This system proactively monitors your KPIs and notifies you when thresholds are exceeded or patterns indicate potential issues.</p>
            </div>

            <h4>🚀 Getting Started</h4>
            <ol class="step-list">
              <li><strong>View Active Alerts</strong> - The dashboard shows all current alerts organized by severity</li>
              <li><strong>Filter Alerts</strong> - Use the dropdown filters to focus on specific categories or severities</li>
              <li><strong>Check Now</strong> - Click "Check Now" to trigger an immediate scan of all KPIs</li>
              <li><strong>Take Action</strong> - Acknowledge, resolve, or dismiss alerts as you address issues</li>
            </ol>

            <h4>📊 Alert Severity Levels</h4>
            <div class="severity-grid">
              <div class="severity-item urgent">
                <span class="badge">Urgent</span>
                <span>Immediate action required - Critical business impact</span>
              </div>
              <div class="severity-item critical">
                <span class="badge">Critical</span>
                <span>High priority - Address within hours</span>
              </div>
              <div class="severity-item warning">
                <span class="badge">Warning</span>
                <span>Monitor closely - Potential issue developing</span>
              </div>
              <div class="severity-item info">
                <span class="badge">Info</span>
                <span>Informational - No immediate action needed</span>
              </div>
            </div>
          </div>

          <!-- Categories Tab -->
          <div v-if="activeGuideTab === 'categories'" class="tab-content">
            <h4>🏷️ Alert Categories</h4>
            <div class="category-list">
              <div class="category-item">
                <strong>📦 On-Time Delivery (OTD)</strong>
                <p>Monitors work orders at risk of missing delivery dates. Triggers when:</p>
                <ul>
                  <li>OTD rate drops below threshold (default: 85%)</li>
                  <li>Work order is approaching due date with insufficient progress</li>
                </ul>
              </div>
              <div class="category-item">
                <strong>✅ Quality</strong>
                <p>Tracks quality metrics including FPY, RTY, PPM, and DPMO. Triggers when:</p>
                <ul>
                  <li>First Pass Yield drops below threshold</li>
                  <li>Defect rate (PPM) exceeds acceptable limits</li>
                </ul>
              </div>
              <div class="category-item">
                <strong>⚡ Efficiency</strong>
                <p>Monitors production efficiency and performance. Triggers when:</p>
                <ul>
                  <li>Efficiency percentage drops below target</li>
                  <li>Performance consistently underperforms</li>
                </ul>
              </div>
              <div class="category-item">
                <strong>👥 Capacity</strong>
                <p>Tracks staffing and capacity utilization. Triggers when:</p>
                <ul>
                  <li>Available workforce insufficient for planned production</li>
                  <li>Floating pool utilization is critically high</li>
                </ul>
              </div>
              <div class="category-item">
                <strong>📅 Attendance</strong>
                <p>Monitors absenteeism patterns using Bradford Factor. Triggers when:</p>
                <ul>
                  <li>Individual Bradford Factor exceeds threshold</li>
                  <li>Team absenteeism rate is unusually high</li>
                </ul>
              </div>
              <div class="category-item">
                <strong>⏸️ Holds</strong>
                <p>Tracks WIP aging and hold duration. Triggers when:</p>
                <ul>
                  <li>Items on hold exceed maximum age threshold</li>
                  <li>High volume of unresolved holds</li>
                </ul>
              </div>
            </div>
          </div>

          <!-- Workflow Tab -->
          <div v-if="activeGuideTab === 'workflow'" class="tab-content">
            <h4>🔄 Alert Lifecycle Workflow</h4>

            <div class="workflow-diagram">
              <div class="workflow-step">
                <span class="step-number">1</span>
                <strong>Generated</strong>
                <p>System detects threshold breach</p>
              </div>
              <div class="workflow-arrow">→</div>
              <div class="workflow-step">
                <span class="step-number">2</span>
                <strong>Active</strong>
                <p>Alert appears in dashboard</p>
              </div>
              <div class="workflow-arrow">→</div>
              <div class="workflow-step">
                <span class="step-number">3</span>
                <strong>Acknowledged</strong>
                <p>User claims ownership</p>
              </div>
              <div class="workflow-arrow">→</div>
              <div class="workflow-step">
                <span class="step-number">4</span>
                <strong>Resolved</strong>
                <p>Issue fixed, notes added</p>
              </div>
            </div>

            <h4>📋 Best Practices</h4>
            <ul class="best-practices">
              <li>✅ <strong>Acknowledge promptly</strong> - Let your team know you're handling the issue</li>
              <li>✅ <strong>Add resolution notes</strong> - Document what was done for future reference</li>
              <li>✅ <strong>Review patterns</strong> - Look for recurring alerts to address root causes</li>
              <li>✅ <strong>Configure thresholds</strong> - Adjust alert thresholds in Admin Settings</li>
              <li>❌ <strong>Don't dismiss without action</strong> - Only dismiss if alert is no longer relevant</li>
            </ul>
          </div>

          <!-- Examples Tab -->
          <div v-if="activeGuideTab === 'examples'" class="tab-content">
            <h4>📝 Example Scenarios</h4>

            <div class="example-card">
              <div class="example-header urgent">Scenario 1: Urgent OTD Alert</div>
              <div class="example-body">
                <p><strong>Alert:</strong> "Work Order WO-2024-001 at risk - Only 60% complete with 2 days remaining"</p>
                <p><strong>Action:</strong></p>
                <ol>
                  <li>Acknowledge the alert</li>
                  <li>Review production schedule</li>
                  <li>Consider adding floating pool workers or overtime</li>
                  <li>Update work order progress</li>
                  <li>Resolve with notes explaining actions taken</li>
                </ol>
              </div>
            </div>

            <div class="example-card">
              <div class="example-header warning">Scenario 2: Quality Warning</div>
              <div class="example-body">
                <p><strong>Alert:</strong> "FPY dropped to 92% - Below 95% threshold"</p>
                <p><strong>Action:</strong></p>
                <ol>
                  <li>Review recent quality entries for patterns</li>
                  <li>Check defect types - is there a common cause?</li>
                  <li>Inspect equipment or materials if needed</li>
                  <li>Implement corrective actions</li>
                  <li>Monitor for improvement before resolving</li>
                </ol>
              </div>
            </div>

            <div class="example-card">
              <div class="example-header critical">Scenario 3: Attendance Critical</div>
              <div class="example-body">
                <p><strong>Alert:</strong> "Team absenteeism at 15% - Exceeds 10% threshold"</p>
                <p><strong>Action:</strong></p>
                <ol>
                  <li>Check floating pool availability</li>
                  <li>Reassign resources if needed</li>
                  <li>Review individual Bradford Factor scores</li>
                  <li>Consider capacity planning adjustments</li>
                </ol>
              </div>
            </div>
          </div>
        </div>
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

// How-to Guide state
const showGuide = ref(false)
const activeGuideTab = ref('quickstart')
const guideTabs = [
  { id: 'quickstart', label: 'Quick Start' },
  { id: 'categories', label: 'Categories' },
  { id: 'workflow', label: 'Workflow' },
  { id: 'examples', label: 'Examples' }
]

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

/* How-to Guide Styles */
.btn-help {
  padding: 0.5rem 1rem;
  background: var(--color-surface);
  border: 1px solid var(--color-primary);
  color: var(--color-primary);
  border-radius: 4px;
  cursor: pointer;
  margin-right: 0.5rem;
}

.btn-help:hover {
  background: var(--color-primary);
  color: white;
}

.guide-dialog {
  max-width: 800px;
  max-height: 80vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.guide-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--color-border);
}

.guide-header h3 {
  margin: 0;
}

.btn-close {
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  padding: 0.25rem 0.5rem;
  line-height: 1;
}

.guide-tabs {
  display: flex;
  gap: 0.5rem;
  padding: 1rem 0;
  border-bottom: 1px solid var(--color-border);
}

.tab-btn {
  padding: 0.5rem 1rem;
  border: none;
  background: var(--color-surface);
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.tab-btn:hover {
  background: var(--color-border);
}

.tab-btn.active {
  background: var(--color-primary);
  color: white;
}

.guide-content {
  overflow-y: auto;
  padding-top: 1rem;
  flex: 1;
}

.tab-content h4 {
  margin: 1rem 0 0.5rem;
}

.info-box {
  background: rgba(59, 130, 246, 0.1);
  border-left: 4px solid #3b82f6;
  padding: 1rem;
  margin-bottom: 1rem;
  border-radius: 0 4px 4px 0;
}

.info-box p {
  margin: 0.5rem 0 0;
}

.step-list {
  padding-left: 1.5rem;
  line-height: 1.8;
}

.step-list li {
  margin-bottom: 0.5rem;
}

.severity-grid {
  display: grid;
  gap: 0.5rem;
  margin-top: 0.5rem;
}

.severity-item {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.75rem;
  border-radius: 4px;
}

.severity-item .badge {
  padding: 0.25rem 0.75rem;
  border-radius: 4px;
  font-weight: bold;
  font-size: 0.875rem;
  min-width: 80px;
  text-align: center;
}

.severity-item.urgent {
  background: rgba(220, 38, 38, 0.1);
}
.severity-item.urgent .badge {
  background: #dc2626;
  color: white;
}

.severity-item.critical {
  background: rgba(234, 88, 12, 0.1);
}
.severity-item.critical .badge {
  background: #ea580c;
  color: white;
}

.severity-item.warning {
  background: rgba(202, 138, 4, 0.1);
}
.severity-item.warning .badge {
  background: #ca8a04;
  color: white;
}

.severity-item.info {
  background: rgba(59, 130, 246, 0.1);
}
.severity-item.info .badge {
  background: #3b82f6;
  color: white;
}

.category-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.category-item {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  padding: 1rem;
  border-radius: 4px;
}

.category-item p {
  margin: 0.5rem 0;
  color: var(--color-text-muted);
}

.category-item ul {
  margin: 0.5rem 0 0;
  padding-left: 1.5rem;
}

.workflow-diagram {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  margin: 1rem 0;
  overflow-x: auto;
}

.workflow-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  min-width: 100px;
}

.step-number {
  width: 32px;
  height: 32px;
  background: var(--color-primary);
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  margin-bottom: 0.5rem;
}

.workflow-step p {
  font-size: 0.75rem;
  color: var(--color-text-muted);
  margin: 0.25rem 0 0;
}

.workflow-arrow {
  font-size: 1.5rem;
  color: var(--color-text-muted);
}

.best-practices {
  list-style: none;
  padding: 0;
}

.best-practices li {
  padding: 0.5rem 0;
  border-bottom: 1px solid var(--color-border);
}

.best-practices li:last-child {
  border-bottom: none;
}

.example-card {
  border: 1px solid var(--color-border);
  border-radius: 4px;
  margin-bottom: 1rem;
  overflow: hidden;
}

.example-header {
  padding: 0.75rem 1rem;
  font-weight: bold;
  color: white;
}

.example-header.urgent {
  background: #dc2626;
}

.example-header.warning {
  background: #ca8a04;
}

.example-header.critical {
  background: #ea580c;
}

.example-body {
  padding: 1rem;
}

.example-body p {
  margin: 0.5rem 0;
}

.example-body ol {
  margin: 0.5rem 0;
  padding-left: 1.5rem;
}
</style>
