/**
 * The calculation-assumption registry: propose, edit, approve, retire, and
 * the append-only change log behind them.
 *
 * The whole site-adjusted half of the dual view is driven by APPROVED
 * assumptions, and none of this lifecycle had a UI -- the only way to create
 * or change one was direct DB access, and the governance trail the backend
 * records was invisible to the people it exists for.
 *
 * Kept free of `useI18n` and of component internals so it can be unit tested;
 * `<script setup>` internals are not reachable through a VTU wrapper, so logic
 * that lives in the view cannot be tested at all.
 */
import { ref, computed } from 'vue'
import api from '@/services/api'
import {
  listAssumptions,
  getCatalog,
  getAssumptionHistory,
  proposeAssumption,
  updateProposal,
  approveAssumption,
  retireAssumption,
  type AssumptionResponse,
  type AssumptionStatus,
  type CatalogEntry,
  type AssumptionChangeRow,
  type ProposalPayload,
  type ProposalPatch,
} from '@/services/api/calculationAssumptions'

export interface ClientOption {
  client_id: string | number
  client_name: string
  [key: string]: unknown
}

/**
 * Who may do what, as the SERVICE enforces it rather than as the route
 * declares it. Each write passes a FastAPI dependency and then a narrower
 * check inside AssumptionService, and only the second is the real answer:
 *
 *   propose   route: supervisory   service: admin | poweruser
 *   edit      route: supervisory   service: the original proposer, or admin
 *   approve   route: planner       service: ADMIN ONLY
 *   retire    route: planner       service: ADMIN ONLY
 *
 * A button gated on the route's tier would be offered to a poweruser and then
 * 403'd, which is the "backend can, UI cannot" defect in reverse.
 */
export const PROPOSER_ROLES = ['admin', 'poweruser']
export const APPROVER_ROLES = ['admin']

export const canPropose = (role: string | undefined | null): boolean =>
  PROPOSER_ROLES.includes(role ?? '')

export const canApprove = (role: string | undefined | null): boolean =>
  APPROVER_ROLES.includes(role ?? '')

/** Only a PROPOSED record is editable; the API answers 409 otherwise. */
export const canEdit = (
  row: Pick<AssumptionResponse, 'status' | 'proposed_by'>,
  userId: string | undefined | null,
  role: string | undefined | null,
): boolean => {
  if (row.status !== 'proposed') return false
  return row.proposed_by === userId || canApprove(role)
}

/**
 * True when the person approving is the person who proposed.
 *
 * The backend permits this -- `approve()` never reads `proposed_by` -- so the
 * screen says so rather than presenting an approval that silently carries no
 * separation of duties. Surfacing it is the honest option while the policy
 * question is open.
 */
export const isSelfApproval = (
  row: Pick<AssumptionResponse, 'proposed_by'>,
  userId: string | undefined | null,
): boolean => Boolean(userId) && row.proposed_by === userId

export function useAssumptionRegistry() {
  const clients = ref<ClientOption[]>([])
  const selectedClient = ref<string | number | null>(null)
  const assumptions = ref<AssumptionResponse[]>([])
  const catalog = ref<CatalogEntry[]>([])
  const history = ref<AssumptionChangeRow[]>([])
  const loading = ref(false)
  const loaded = ref(false)
  /** Retired records are history, so they are hidden until asked for. */
  const includeRetired = ref(false)

  const selectedClientInfo = computed<ClientOption | null>(
    () => clients.value.find((c) => c.client_id === selectedClient.value) ?? null,
  )

  const visible = computed<AssumptionResponse[]>(() =>
    includeRetired.value
      ? assumptions.value
      : assumptions.value.filter((a) => a.status !== 'retired'),
  )

  /**
   * Proposals waiting on an approver. This is the screen's call to action --
   * without it a reader has to scan every row to find the one that needs a
   * decision.
   */
  const pending = computed<AssumptionResponse[]>(() =>
    assumptions.value.filter((a) => a.status === 'proposed'),
  )

  const byStatus = computed<Record<AssumptionStatus, number>>(() => {
    const counts = { proposed: 0, active: 0, retired: 0 } as Record<AssumptionStatus, number>
    for (const a of assumptions.value) {
      if (a.status in counts) counts[a.status] += 1
    }
    return counts
  })

  /** Catalog entry for a name, which carries the allowed values. */
  const catalogFor = (name: string): CatalogEntry | undefined =>
    catalog.value.find((c) => c.name === name)

  const loadClients = async (): Promise<void> => {
    const res = await api.getClients()
    clients.value = (res.data as ClientOption[]) || []
  }

  const loadCatalog = async (): Promise<void> => {
    const { data } = await getCatalog()
    catalog.value = (data as CatalogEntry[]) ?? []
  }

  const load = async (): Promise<void> => {
    if (!selectedClient.value) {
      assumptions.value = []
      loaded.value = false
      return
    }
    loading.value = true
    try {
      // include_inactive so retired records are available to show; the
      // `visible` computed decides whether they are on screen.
      const { data } = await listAssumptions({
        client_id: String(selectedClient.value),
        include_inactive: true,
      })
      assumptions.value = (data as AssumptionResponse[]) ?? []
      loaded.value = true
    } catch (error) {
      assumptions.value = []
      loaded.value = false
      throw error
    } finally {
      loading.value = false
    }
  }

  const loadHistory = async (assumptionId: number): Promise<AssumptionChangeRow[]> => {
    const { data } = await getAssumptionHistory(assumptionId)
    history.value = (data as AssumptionChangeRow[]) ?? []
    return history.value
  }

  const propose = async (payload: ProposalPayload): Promise<void> => {
    await proposeAssumption(payload)
    await load()
  }

  const edit = async (assumptionId: number, patch: ProposalPatch): Promise<void> => {
    await updateProposal(assumptionId, patch)
    await load()
  }

  const approve = async (assumptionId: number, changeReason?: string | null): Promise<void> => {
    await approveAssumption(assumptionId, changeReason)
    await load()
  }

  const retire = async (assumptionId: number, changeReason?: string | null): Promise<void> => {
    await retireAssumption(assumptionId, changeReason)
    await load()
  }

  return {
    clients,
    selectedClient,
    assumptions,
    catalog,
    history,
    loading,
    loaded,
    includeRetired,
    selectedClientInfo,
    visible,
    pending,
    byStatus,
    catalogFor,
    loadClients,
    loadCatalog,
    load,
    loadHistory,
    propose,
    edit,
    approve,
    retire,
  }
}
