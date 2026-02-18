<template>
  <div class="alert-dashboard">
    <!-- Summary Header -->
    <div class="alert-summary-header">
      <div class="summary-stats">
        <div class="stat urgent" v-if="summary.urgent_count > 0">
          <span class="count">{{ summary.urgent_count }}</span>
          <span class="label">{{ t('alerts.urgent') }}</span>
        </div>
        <div class="stat critical" v-if="summary.critical_count > 0">
          <span class="count">{{ summary.critical_count }}</span>
          <span class="label">{{ t('alerts.critical') }}</span>
        </div>
        <div class="stat warning" v-if="summary.by_severity?.warning > 0">
          <span class="count">{{ summary.by_severity.warning }}</span>
          <span class="label">{{ t('alerts.warning') }}</span>
        </div>
        <div class="stat info" v-if="summary.by_severity?.info > 0">
          <span class="count">{{ summary.by_severity.info }}</span>
          <span class="label">{{ t('alerts.info') }}</span>
        </div>
        <div class="stat total">
          <span class="count">{{ summary.total_active }}</span>
          <span class="label">{{ t('alerts.totalActive') }}</span>
        </div>
      </div>
      <div class="actions">
        <button @click="showGuide = true" class="btn-help">
          <span>{{ t('alerts.howToUse') }}</span>
        </button>
        <button @click="generateAlerts" :disabled="generating" class="btn-generate">
          <span v-if="generating">{{ t('alerts.checking') }}</span>
          <span v-else>{{ t('alerts.checkNow') }}</span>
        </button>
      </div>
    </div>

    <!-- Filters -->
    <div class="alert-filters">
      <select v-model="filters.category" @change="loadAlerts">
        <option value="">{{ t('alerts.allCategories') }}</option>
        <option value="otd">{{ t('alerts.categoryOtd') }}</option>
        <option value="quality">{{ t('alerts.categoryQuality') }}</option>
        <option value="efficiency">{{ t('alerts.categoryEfficiency') }}</option>
        <option value="capacity">{{ t('alerts.categoryCapacity') }}</option>
        <option value="attendance">{{ t('alerts.categoryAttendance') }}</option>
        <option value="hold">{{ t('alerts.categoryHold') }}</option>
      </select>
      <select v-model="filters.severity" @change="loadAlerts">
        <option value="">{{ t('alerts.allSeverities') }}</option>
        <option value="urgent">{{ t('alerts.urgent') }}</option>
        <option value="critical">{{ t('alerts.critical') }}</option>
        <option value="warning">{{ t('alerts.warning') }}</option>
        <option value="info">{{ t('alerts.info') }}</option>
      </select>
      <select v-model="filters.status" @change="loadAlerts">
        <option value="active">{{ t('alerts.active') }}</option>
        <option value="acknowledged">{{ t('alerts.acknowledged') }}</option>
        <option value="resolved">{{ t('alerts.resolved') }}</option>
        <option value="">{{ t('common.all') }}</option>
      </select>
    </div>

    <!-- Urgent Alerts Section -->
    <div v-if="urgentAlerts.length > 0" class="alert-section urgent-section">
      <h3>{{ t('alerts.urgentAlerts') }}</h3>
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
      <h3>{{ t('alerts.criticalAlerts') }}</h3>
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
      <h3>{{ t('alerts.allAlerts') }} ({{ alerts.length }})</h3>
      <div v-if="loading" class="loading">{{ t('alerts.loadingAlerts') }}</div>
      <div v-else-if="alerts.length === 0" class="no-alerts">
        {{ t('alerts.noAlertsMatching') }}
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
    <AlertGuideDialog v-model="showGuide" />

    <!-- Resolve Dialog -->
    <AlertResolveDialog
      :modelValue="showResolveDialog"
      :alert="resolvingAlert"
      :notes="resolutionNotes"
      @update:notes="resolutionNotes = $event"
      @close="closeResolveDialog"
      @confirm="confirmResolve"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import AlertCard from './AlertCard.vue'
import AlertGuideDialog from './AlertGuideDialog.vue'
import AlertResolveDialog from './AlertResolveDialog.vue'
import useAlertDashboardData from '@/composables/useAlertDashboardData'
import useAlertDashboardActions from '@/composables/useAlertDashboardActions'

const { t } = useI18n()

const {
  alerts,
  summary,
  loading,
  filters,
  urgentAlerts,
  criticalAlerts,
  loadAlerts,
  loadSummary
} = useAlertDashboardData()

const {
  generating,
  showResolveDialog,
  resolvingAlert,
  resolutionNotes,
  generateAlerts,
  handleAcknowledge,
  handleResolve,
  confirmResolve,
  closeResolveDialog,
  handleDismiss
} = useAlertDashboardActions({ loadAlerts, loadSummary })

const showGuide = ref(false)

onMounted(() => {
  loadAlerts()
  loadSummary()
})
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
</style>
