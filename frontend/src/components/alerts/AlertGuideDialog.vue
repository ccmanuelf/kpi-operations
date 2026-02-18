<template>
  <div v-if="modelValue" class="dialog-overlay" @click.self="$emit('update:modelValue', false)">
    <div class="dialog guide-dialog">
      <div class="guide-header">
        <h3>{{ t('alerts.guide.title') }}</h3>
        <button @click="$emit('update:modelValue', false)" class="btn-close">&times;</button>
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
            <strong>{{ t('alerts.guide.welcomeTitle') }}</strong>
            <p>{{ t('alerts.guide.welcomeDescription') }}</p>
          </div>

          <h4>{{ t('alerts.guide.gettingStarted') }}</h4>
          <ol class="step-list">
            <li>{{ t('alerts.guide.step1') }}</li>
            <li>{{ t('alerts.guide.step2') }}</li>
            <li>{{ t('alerts.guide.step3') }}</li>
            <li>{{ t('alerts.guide.step4') }}</li>
          </ol>

          <h4>{{ t('alerts.guide.severityLevels') }}</h4>
          <div class="severity-grid">
            <div class="severity-item urgent">
              <span class="badge">{{ t('alerts.urgent') }}</span>
              <span>{{ t('alerts.guide.urgentDesc') }}</span>
            </div>
            <div class="severity-item critical">
              <span class="badge">{{ t('alerts.critical') }}</span>
              <span>{{ t('alerts.guide.criticalDesc') }}</span>
            </div>
            <div class="severity-item warning">
              <span class="badge">{{ t('alerts.warning') }}</span>
              <span>{{ t('alerts.guide.warningDesc') }}</span>
            </div>
            <div class="severity-item info">
              <span class="badge">{{ t('alerts.info') }}</span>
              <span>{{ t('alerts.guide.infoDesc') }}</span>
            </div>
          </div>
        </div>

        <!-- Categories Tab -->
        <div v-if="activeGuideTab === 'categories'" class="tab-content">
          <h4>{{ t('alerts.guide.alertCategories') }}</h4>
          <div class="category-list">
            <div class="category-item">
              <strong>{{ t('alerts.guide.otdTitle') }}</strong>
              <p>{{ t('alerts.guide.otdDesc') }}</p>
              <ul>
                <li>{{ t('alerts.guide.otdTrigger1') }}</li>
                <li>{{ t('alerts.guide.otdTrigger2') }}</li>
              </ul>
            </div>
            <div class="category-item">
              <strong>{{ t('alerts.guide.qualityTitle') }}</strong>
              <p>{{ t('alerts.guide.qualityDesc') }}</p>
              <ul>
                <li>{{ t('alerts.guide.qualityTrigger1') }}</li>
                <li>{{ t('alerts.guide.qualityTrigger2') }}</li>
              </ul>
            </div>
            <div class="category-item">
              <strong>{{ t('alerts.guide.efficiencyTitle') }}</strong>
              <p>{{ t('alerts.guide.efficiencyDesc') }}</p>
              <ul>
                <li>{{ t('alerts.guide.efficiencyTrigger1') }}</li>
                <li>{{ t('alerts.guide.efficiencyTrigger2') }}</li>
              </ul>
            </div>
            <div class="category-item">
              <strong>{{ t('alerts.guide.capacityTitle') }}</strong>
              <p>{{ t('alerts.guide.capacityDesc') }}</p>
              <ul>
                <li>{{ t('alerts.guide.capacityTrigger1') }}</li>
                <li>{{ t('alerts.guide.capacityTrigger2') }}</li>
              </ul>
            </div>
            <div class="category-item">
              <strong>{{ t('alerts.guide.attendanceTitle') }}</strong>
              <p>{{ t('alerts.guide.attendanceDesc') }}</p>
              <ul>
                <li>{{ t('alerts.guide.attendanceTrigger1') }}</li>
                <li>{{ t('alerts.guide.attendanceTrigger2') }}</li>
              </ul>
            </div>
            <div class="category-item">
              <strong>{{ t('alerts.guide.holdsTitle') }}</strong>
              <p>{{ t('alerts.guide.holdsDesc') }}</p>
              <ul>
                <li>{{ t('alerts.guide.holdsTrigger1') }}</li>
                <li>{{ t('alerts.guide.holdsTrigger2') }}</li>
              </ul>
            </div>
          </div>
        </div>

        <!-- Workflow Tab -->
        <div v-if="activeGuideTab === 'workflow'" class="tab-content">
          <h4>{{ t('alerts.guide.lifecycleTitle') }}</h4>

          <div class="workflow-diagram">
            <div class="workflow-step">
              <span class="step-number">1</span>
              <strong>{{ t('alerts.guide.stepGenerated') }}</strong>
              <p>{{ t('alerts.guide.stepGeneratedDesc') }}</p>
            </div>
            <div class="workflow-arrow">&rarr;</div>
            <div class="workflow-step">
              <span class="step-number">2</span>
              <strong>{{ t('alerts.guide.stepActive') }}</strong>
              <p>{{ t('alerts.guide.stepActiveDesc') }}</p>
            </div>
            <div class="workflow-arrow">&rarr;</div>
            <div class="workflow-step">
              <span class="step-number">3</span>
              <strong>{{ t('alerts.guide.stepAcknowledged') }}</strong>
              <p>{{ t('alerts.guide.stepAcknowledgedDesc') }}</p>
            </div>
            <div class="workflow-arrow">&rarr;</div>
            <div class="workflow-step">
              <span class="step-number">4</span>
              <strong>{{ t('alerts.guide.stepResolved') }}</strong>
              <p>{{ t('alerts.guide.stepResolvedDesc') }}</p>
            </div>
          </div>

          <h4>{{ t('alerts.guide.bestPractices') }}</h4>
          <ul class="best-practices">
            <li>{{ t('alerts.guide.bp1') }}</li>
            <li>{{ t('alerts.guide.bp2') }}</li>
            <li>{{ t('alerts.guide.bp3') }}</li>
            <li>{{ t('alerts.guide.bp4') }}</li>
            <li>{{ t('alerts.guide.bp5') }}</li>
          </ul>
        </div>

        <!-- Examples Tab -->
        <div v-if="activeGuideTab === 'examples'" class="tab-content">
          <h4>{{ t('alerts.guide.exampleScenarios') }}</h4>

          <div class="example-card">
            <div class="example-header urgent">{{ t('alerts.guide.scenario1Title') }}</div>
            <div class="example-body">
              <p><strong>{{ t('alerts.guide.scenario1Action') }}</strong> "{{ t('alerts.guide.scenario1Alert') }}"</p>
              <ol>
                <li>{{ t('alerts.guide.scenario1Step1') }}</li>
                <li>{{ t('alerts.guide.scenario1Step2') }}</li>
                <li>{{ t('alerts.guide.scenario1Step3') }}</li>
                <li>{{ t('alerts.guide.scenario1Step4') }}</li>
                <li>{{ t('alerts.guide.scenario1Step5') }}</li>
              </ol>
            </div>
          </div>

          <div class="example-card">
            <div class="example-header warning">{{ t('alerts.guide.scenario2Title') }}</div>
            <div class="example-body">
              <p><strong>{{ t('alerts.guide.scenario2Action') }}</strong> "{{ t('alerts.guide.scenario2Alert') }}"</p>
              <ol>
                <li>{{ t('alerts.guide.scenario2Step1') }}</li>
                <li>{{ t('alerts.guide.scenario2Step2') }}</li>
                <li>{{ t('alerts.guide.scenario2Step3') }}</li>
                <li>{{ t('alerts.guide.scenario2Step4') }}</li>
                <li>{{ t('alerts.guide.scenario2Step5') }}</li>
              </ol>
            </div>
          </div>

          <div class="example-card">
            <div class="example-header critical">{{ t('alerts.guide.scenario3Title') }}</div>
            <div class="example-body">
              <p><strong>{{ t('alerts.guide.scenario3Action') }}</strong> "{{ t('alerts.guide.scenario3Alert') }}"</p>
              <ol>
                <li>{{ t('alerts.guide.scenario3Step1') }}</li>
                <li>{{ t('alerts.guide.scenario3Step2') }}</li>
                <li>{{ t('alerts.guide.scenario3Step3') }}</li>
                <li>{{ t('alerts.guide.scenario3Step4') }}</li>
              </ol>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

defineProps({
  modelValue: {
    type: Boolean,
    default: false
  }
})

defineEmits(['update:modelValue'])

const activeGuideTab = ref('quickstart')
const guideTabs = computed(() => [
  { id: 'quickstart', label: t('alerts.guide.quickStart') },
  { id: 'categories', label: t('alerts.guide.categories') },
  { id: 'workflow', label: t('alerts.guide.workflow') },
  { id: 'examples', label: t('alerts.guide.examples') }
])
</script>

<style scoped>
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

.severity-item.urgent { background: rgba(220, 38, 38, 0.1); }
.severity-item.urgent .badge { background: #dc2626; color: white; }
.severity-item.critical { background: rgba(234, 88, 12, 0.1); }
.severity-item.critical .badge { background: #ea580c; color: white; }
.severity-item.warning { background: rgba(202, 138, 4, 0.1); }
.severity-item.warning .badge { background: #ca8a04; color: white; }
.severity-item.info { background: rgba(59, 130, 246, 0.1); }
.severity-item.info .badge { background: #3b82f6; color: white; }

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

.example-header.urgent { background: #dc2626; }
.example-header.warning { background: #ca8a04; }
.example-header.critical { background: #ea580c; }

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
