<template>
  <v-container fluid class="pa-4">
    <v-row>
      <v-col cols="12">
        <h1 class="text-h4 mb-2">
          <v-icon class="mr-2">mdi-scale-balance</v-icon>
          {{ t('admin.assumptions.title') }}
        </h1>
        <p class="text-subtitle-1 text-medium-emphasis">
          {{ t('admin.assumptions.subtitle') }}
        </p>
      </v-col>
    </v-row>

    <v-row class="mt-2">
      <v-col cols="12" md="4">
        <v-select
          v-model="selectedClient"
          :items="clients"
          item-title="client_name"
          item-value="client_id"
          :label="t('filters.client')"
          variant="outlined"
          density="comfortable"
          prepend-inner-icon="mdi-domain"
          @update:model-value="reload"
        />
      </v-col>
      <v-col cols="12" md="8" class="d-flex align-center gap-2">
        <v-btn
          color="primary"
          prepend-icon="mdi-plus"
          :disabled="!selectedClient || !mayPropose"
          data-testid="propose-assumption"
          @click="openPropose"
        >
          {{ t('admin.assumptions.propose') }}
        </v-btn>
        <span v-if="!mayPropose" class="text-caption text-medium-emphasis">
          {{ t('admin.assumptions.needsPlanner') }}
        </span>
        <v-spacer />
        <v-switch
          v-model="includeRetired"
          :label="t('admin.assumptions.showRetired')"
          density="compact"
          hide-details
          color="primary"
        />
      </v-col>
    </v-row>

    <!-- The call to action: proposals waiting on a decision. -->
    <v-row v-if="pending.length" class="mt-2">
      <v-col cols="12">
        <v-alert type="info" variant="tonal" density="compact" data-testid="pending-banner">
          <v-icon class="mr-2">mdi-clock-alert-outline</v-icon>
          {{ t('admin.assumptions.pendingBanner', { count: pending.length }) }}
        </v-alert>
      </v-col>
    </v-row>

    <v-row class="mt-2">
      <v-col cols="12">
        <v-card>
          <v-data-table
            :headers="headers"
            :items="visible"
            :loading="loading"
            class="elevation-0"
            :no-data-text="t('admin.assumptions.noneForClient')"
          >
            <template v-slot:item.status="{ item }">
              <v-chip :color="statusColor(item.status)" size="small" data-testid="status-chip">
                {{ t(`admin.assumptions.status.${item.status}`) }}
              </v-chip>
            </template>
            <template v-slot:item.value="{ item }">
              <code>{{ formatValue(item.value) }}</code>
            </template>
            <template v-slot:item.rationale="{ item }">
              <span v-if="item.rationale">{{ item.rationale }}</span>
              <span v-else class="text-medium-emphasis font-italic">
                {{ t('admin.assumptions.noRationale') }}
              </span>
            </template>
            <template v-slot:item.actions="{ item }">
              <div class="d-flex gap-1">
                <v-btn
                  size="x-small"
                  variant="text"
                  icon="mdi-history"
                  :title="t('admin.assumptions.viewHistory')"
                  data-testid="view-history"
                  @click="openHistory(item)"
                />
                <v-btn
                  v-if="mayEdit(item)"
                  size="x-small"
                  variant="text"
                  icon="mdi-pencil"
                  :title="t('admin.assumptions.edit')"
                  @click="openEdit(item)"
                />
                <v-btn
                  v-if="item.status === 'proposed' && mayApprove"
                  size="x-small"
                  variant="text"
                  color="success"
                  icon="mdi-check-decagram"
                  :title="t('admin.assumptions.approve')"
                  data-testid="approve-assumption"
                  @click="openApprove(item)"
                />
                <v-btn
                  v-if="item.status === 'active' && mayApprove"
                  size="x-small"
                  variant="text"
                  color="warning"
                  icon="mdi-archive-arrow-down"
                  :title="t('admin.assumptions.retire')"
                  data-testid="retire-assumption"
                  @click="openRetire(item)"
                />
              </div>
            </template>
          </v-data-table>
        </v-card>
      </v-col>
    </v-row>

    <!-- Propose / edit -->
    <v-dialog v-model="formDialog" max-width="620" persistent scrollable>
      <v-card>
        <v-card-title>
          {{ editing ? t('admin.assumptions.editTitle') : t('admin.assumptions.proposeTitle') }}
        </v-card-title>
        <v-card-text>
          <v-select
            v-model="form.assumption_name"
            :items="catalogNames"
            :label="t('admin.assumptions.name')"
            :disabled="Boolean(editing)"
            variant="outlined"
            density="comfortable"
          />
          <p v-if="selectedCatalogEntry" class="text-caption text-medium-emphasis mb-3">
            {{ selectedCatalogEntry.description }}
          </p>
          <v-select
            v-if="allowedValues.length"
            v-model="form.value"
            :items="allowedValues"
            :label="t('admin.assumptions.value')"
            variant="outlined"
            density="comfortable"
          />
          <v-text-field
            v-else
            v-model="form.value"
            :label="t('admin.assumptions.value')"
            variant="outlined"
            density="comfortable"
          />
          <v-textarea
            v-model="form.rationale"
            :label="t('admin.assumptions.rationale')"
            :hint="t('admin.assumptions.rationaleHint')"
            persistent-hint
            rows="3"
            variant="outlined"
            density="comfortable"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="formDialog = false">{{ t('common.cancel') }}</v-btn>
          <v-btn
            color="primary"
            :loading="saving"
            :disabled="!form.assumption_name || form.value === null || form.value === ''"
            data-testid="submit-proposal"
            @click="submitForm"
          >
            {{ t('common.save') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Approve / retire -->
    <v-dialog v-model="decisionDialog" max-width="560">
      <v-card>
        <v-card-title>
          {{ decision === 'approve' ? t('admin.assumptions.approveTitle') : t('admin.assumptions.retireTitle') }}
        </v-card-title>
        <v-card-text>
          <p class="mb-3">
            {{ t('admin.assumptions.decisionBody', {
              name: decisionTarget?.assumption_name ?? '',
              value: formatValue(decisionTarget?.value),
            }) }}
          </p>
          <!-- The backend permits an admin to approve their own proposal --
               approve() never reads proposed_by. Say so rather than present
               an approval that silently carries no separation of duties. -->
          <v-alert
            v-if="decision === 'approve' && selfApproving"
            type="warning"
            variant="tonal"
            density="compact"
            class="mb-3"
            data-testid="self-approval-warning"
          >
            {{ t('admin.assumptions.selfApprovalWarning') }}
          </v-alert>
          <v-alert
            v-if="decision === 'retire'"
            type="warning"
            variant="tonal"
            density="compact"
            class="mb-3"
          >
            {{ t('admin.assumptions.retireWarning') }}
          </v-alert>
          <v-textarea
            v-model="changeReason"
            :label="t('admin.assumptions.changeReason')"
            :hint="t('admin.assumptions.changeReasonHint')"
            persistent-hint
            rows="2"
            variant="outlined"
            density="comfortable"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="decisionDialog = false">{{ t('common.cancel') }}</v-btn>
          <v-btn
            :color="decision === 'approve' ? 'success' : 'warning'"
            :loading="deciding"
            data-testid="confirm-decision"
            @click="submitDecision"
          >
            {{ decision === 'approve' ? t('admin.assumptions.approve') : t('admin.assumptions.retire') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- The governance trail -->
    <v-dialog v-model="historyDialog" max-width="820" scrollable>
      <v-card>
        <v-card-title>
          <v-icon class="mr-2">mdi-history</v-icon>
          {{ t('admin.assumptions.historyTitle', { name: historyTarget?.assumption_name ?? '' }) }}
        </v-card-title>
        <v-card-text>
          <v-timeline v-if="history.length" density="compact" side="end">
            <v-timeline-item
              v-for="row in history"
              :key="row.change_id"
              size="x-small"
              :dot-color="statusColor(row.new_status)"
            >
              <div class="text-body-2">
                <strong>{{ row.previous_status ?? '—' }} → {{ row.new_status ?? '—' }}</strong>
                {{ t('admin.assumptions.historyBy', { who: row.changed_by, when: formatDate(row.changed_at) }) }}
              </div>
              <div v-if="row.previous_value !== null || row.new_value !== null" class="text-caption">
                <code>{{ formatValue(row.previous_value) }}</code> →
                <code>{{ formatValue(row.new_value) }}</code>
              </div>
              <div v-if="row.change_reason" class="text-caption text-medium-emphasis">
                {{ row.change_reason }}
              </div>
            </v-timeline-item>
          </v-timeline>
          <p v-else class="text-medium-emphasis">{{ t('admin.assumptions.noHistory') }}</p>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="historyDialog = false">{{ t('common.close') }}</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup>
/**
 * AssumptionRegistry — the propose / approve / retire lifecycle and the
 * append-only change log behind it.
 *
 * The site-adjusted half of the dual view is driven entirely by APPROVED
 * assumptions, and none of this had a UI: no user, admin included, could
 * create, edit, approve or retire one from the product, so the only route was
 * direct DB access. The governance trail the backend carefully records was
 * likewise invisible to the people it exists for.
 *
 * Permissions follow the SERVICE, not the route. Each write passes a FastAPI
 * dependency and then a narrower check inside AssumptionService: propose is
 * admin+poweruser where the route says supervisory, and approve/retire are
 * ADMIN ONLY where the route says planner. Gating a button on the route's tier
 * would offer approve to a poweruser and then 403 them.
 */
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useNotificationStore } from '@/stores/notificationStore'
import { useAuthStore } from '@/stores/authStore'
import {
  useAssumptionRegistry,
  canPropose,
  canApprove,
  canEdit,
  isSelfApproval,
} from '@/composables/useAssumptionRegistry'
import { formatLocaleDate } from '@/utils/localeDate'

const { t } = useI18n()
const notify = useNotificationStore()
const auth = useAuthStore()

const {
  clients,
  selectedClient,
  catalog,
  history,
  loading,
  includeRetired,
  visible,
  pending,
  catalogFor,
  loadClients,
  loadCatalog,
  load,
  loadHistory,
  propose,
  edit,
  approve,
  retire,
} = useAssumptionRegistry()

const formDialog = ref(false)
const decisionDialog = ref(false)
const historyDialog = ref(false)
const saving = ref(false)
const deciding = ref(false)
const editing = ref(null)
const decision = ref('approve')
const decisionTarget = ref(null)
const historyTarget = ref(null)
const changeReason = ref('')
const form = ref({ assumption_name: '', value: '', rationale: '' })

const mayPropose = computed(() => canPropose(auth.user?.role))
const mayApprove = computed(() => canApprove(auth.user?.role))
const mayEdit = (row) => canEdit(row, auth.user?.user_id, auth.user?.role)
const selfApproving = computed(() =>
  decisionTarget.value ? isSelfApproval(decisionTarget.value, auth.user?.user_id) : false,
)

const catalogNames = computed(() => catalog.value.map((c) => c.name))
const selectedCatalogEntry = computed(() => catalogFor(form.value.assumption_name))
const allowedValues = computed(() => {
  const allowed = selectedCatalogEntry.value?.allowed_values
  return Array.isArray(allowed) ? allowed.map((v) => String(v)) : []
})

const headers = computed(() => [
  { title: t('admin.assumptions.name'), key: 'assumption_name' },
  { title: t('admin.assumptions.value'), key: 'value' },
  { title: t('admin.assumptions.statusHeader'), key: 'status' },
  { title: t('admin.assumptions.rationale'), key: 'rationale' },
  { title: t('admin.assumptions.proposedBy'), key: 'proposed_by' },
  { title: t('common.actions'), key: 'actions', sortable: false },
])

const statusColor = (status) =>
  ({ proposed: 'info', active: 'success', retired: 'grey' })[status] ?? 'grey'

const formatValue = (value) =>
  value === null || value === undefined ? '—' : typeof value === 'string' ? value : JSON.stringify(value)

const formatDate = (iso) => (iso ? formatLocaleDate(iso) : '')

const reload = async () => {
  try {
    await load()
  } catch {
    notify.showError(t('errors.general'))
  }
}

const openPropose = () => {
  editing.value = null
  form.value = { assumption_name: '', value: '', rationale: '' }
  formDialog.value = true
}

const openEdit = (row) => {
  editing.value = row
  form.value = {
    assumption_name: row.assumption_name,
    value: typeof row.value === 'string' ? row.value : JSON.stringify(row.value),
    rationale: row.rationale ?? '',
  }
  formDialog.value = true
}

const openApprove = (row) => {
  decision.value = 'approve'
  decisionTarget.value = row
  changeReason.value = ''
  decisionDialog.value = true
}

const openRetire = (row) => {
  decision.value = 'retire'
  decisionTarget.value = row
  changeReason.value = ''
  decisionDialog.value = true
}

const openHistory = async (row) => {
  historyTarget.value = row
  historyDialog.value = true
  try {
    await loadHistory(row.assumption_id)
  } catch {
    notify.showError(t('errors.general'))
  }
}

const submitForm = async () => {
  saving.value = true
  try {
    if (editing.value) {
      await edit(editing.value.assumption_id, {
        value: form.value.value,
        rationale: form.value.rationale || null,
      })
      notify.showSuccess(t('admin.assumptions.proposalUpdated'))
    } else {
      await propose({
        client_id: String(selectedClient.value),
        assumption_name: form.value.assumption_name,
        value: form.value.value,
        rationale: form.value.rationale || null,
      })
      notify.showSuccess(t('admin.assumptions.proposalCreated'))
    }
    formDialog.value = false
  } catch (error) {
    notify.showError(error?.response?.data?.detail || t('errors.general'))
  } finally {
    saving.value = false
  }
}

const submitDecision = async () => {
  if (!decisionTarget.value) return
  deciding.value = true
  try {
    if (decision.value === 'approve') {
      await approve(decisionTarget.value.assumption_id, changeReason.value || null)
      notify.showSuccess(t('admin.assumptions.approved'))
    } else {
      await retire(decisionTarget.value.assumption_id, changeReason.value || null)
      notify.showSuccess(t('admin.assumptions.retired'))
    }
    decisionDialog.value = false
  } catch (error) {
    notify.showError(error?.response?.data?.detail || t('errors.general'))
  } finally {
    deciding.value = false
  }
}

onMounted(async () => {
  try {
    await Promise.all([loadClients(), loadCatalog()])
  } catch {
    notify.showError(t('errors.general'))
  }
})
</script>

<style scoped>
.gap-1 {
  gap: 4px;
}
.gap-2 {
  gap: 8px;
}
</style>
