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

/**
 * Coerce a form value to the type the catalog declares.
 *
 * The form is text, so every value arrives as a string. Five of the six
 * assumptions are enumerated strings and round-trip cleanly, but
 * `otd_carrier_buffer_pct` is an integer with no allowed_values -- it renders
 * as a free-text field, and sending it verbatim stores the JSON string "15"
 * where the column should hold the number 15. Nothing raises today, because
 * both the variance report and the OTD service coerce with `str()` on the way
 * back out, but the stored value contradicts its own catalog entry and would
 * break the first consumer that does arithmetic without coercing.
 *
 * Worse, that assumption has NO allowed_values, so the backend validates
 * nothing: "abc" would be accepted here and only fail later, inside the OTD
 * calculation, as a Decimal conversion error far from the screen that caused
 * it.
 *
 * Returns `null` when the text cannot be the declared type, so the caller can
 * refuse rather than send it.
 */
export const coerceToCatalogType = (
  raw: unknown,
  entry: Pick<CatalogEntry, 'default_value'> | undefined,
): unknown | null => {
  const standard = entry?.default_value
  if (typeof standard === 'number') {
    const text = String(raw ?? '').trim()
    if (!/^-?\d+(\.\d+)?$/.test(text)) return null
    const value = Number(text)
    return Number.isFinite(value) ? value : null
  }
  if (typeof standard === 'boolean') {
    const text = String(raw ?? '').trim().toLowerCase()
    if (text === 'true') return true
    if (text === 'false') return false
    return null
  }
  return raw
}

export function useAssumptionRegistry() {
  const clients = ref<ClientOption[]>([])
  const selectedClient = ref<string | number | null>(null)
  const assumptions = ref<AssumptionResponse[]>([])
  const catalog = ref<CatalogEntry[]>([])
  const history = ref<AssumptionChangeRow[]>([])
  const loading = ref(false)
  const loaded = ref(false)
  /** Set when a write committed but the follow-up read failed. */
  const staleAfterWrite = ref(false)
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

  //: Identifies the most recent read. Comparing the CLIENT was not enough:
  //: switching A -> B -> A lets the first request match again on arrival and
  //: overwrite the third request's newer rows with its own older ones. A
  //: monotonic token is the only thing that distinguishes two reads of the
  //: same client.
  let readToken = 0

  /**
   * Returns TRUE only when this read applied its data.
   *
   * A superseded read returns false rather than throwing, and a read with no
   * client selected never runs at all -- so a caller that needs to know
   * whether the list on screen actually reflects a write cannot infer it from
   * the absence of an exception.
   */
  const load = async (): Promise<boolean> => {
    if (!selectedClient.value) {
      // Bump the token here too. Clearing the selection must SUPERSEDE any
      // read still in flight -- without this it keeps `token === readToken`,
      // lands, and repopulates the table for a client that is no longer
      // selected.
      readToken += 1
      assumptions.value = []
      loaded.value = false
      loading.value = false
      return false
    }
    const token = ++readToken
    const requestedFor = String(selectedClient.value)
    loading.value = true
    try {
      // include_inactive so retired records are available to show; the
      // `visible` computed decides whether they are on screen.
      const { data } = await listAssumptions({
        client_id: requestedFor,
        include_inactive: true,
      })
      // Superseded: a newer read is in flight or has already landed. Applying
      // this one would show a tenant's rows under another's name, or roll the
      // list back to a state from before the newest read.
      if (token !== readToken) return false
      assumptions.value = (data as AssumptionResponse[]) ?? []
      loaded.value = true
      // A read that succeeded is the freshest state there is, so any earlier
      // "could not refresh" warning no longer describes what is on screen.
      staleAfterWrite.value = false
      return true
    } catch (error) {
      // A superseded failure must not clear the newer rows either -- and must
      // not be reported to this read's caller as ITS failure.
      if (token !== readToken) return false
      assumptions.value = []
      loaded.value = false
      throw error
    } finally {
      if (token === readToken) loading.value = false
    }
  }

  //: Same shape as `readToken`, for the same reason. Opening one row's
  //: history and then another's can resolve out of order, and this is an
  //: AUDIT view -- showing one assumption's change log under another's name
  //: is the specific thing it must never do.
  let historyToken = 0

  const loadHistory = async (assumptionId: number): Promise<AssumptionChangeRow[]> => {
    const token = ++historyToken
    const { data } = await getAssumptionHistory(assumptionId)
    const rows = (data as AssumptionChangeRow[]) ?? []
    if (token !== historyToken) return history.value
    history.value = rows
    return rows
  }

  /**
   * Refresh after a successful write, WITHOUT letting a failed refresh look
   * like a failed write.
   *
   * `await write(); await load()` in one try block reports a read error as if
   * the mutation had failed -- so the operator retries a proposal that already
   * exists, and gets a duplicate or a 409. The write has committed by the time
   * we get here; the worst a failed reload can do is leave the list stale, and
   * `staleAfterWrite` says so.
   */
  const refreshAfterWrite = async (): Promise<void> => {
    try {
      // `load` clears the flag itself when it applies. A read that was
      // superseded, or that never ran because no client is selected, returns
      // false without throwing -- and treating that as a successful refresh
      // would tell the operator the list reflects their write when it does
      // not. A newer read clears the flag again when it lands.
      if (!(await load())) staleAfterWrite.value = true
    } catch {
      staleAfterWrite.value = true
    }
  }

  const propose = async (payload: ProposalPayload): Promise<void> => {
    await proposeAssumption(payload)
    await refreshAfterWrite()
  }

  const edit = async (assumptionId: number, patch: ProposalPatch): Promise<void> => {
    await updateProposal(assumptionId, patch)
    await refreshAfterWrite()
  }

  const approve = async (assumptionId: number, changeReason?: string | null): Promise<void> => {
    await approveAssumption(assumptionId, changeReason)
    await refreshAfterWrite()
  }

  const retire = async (assumptionId: number, changeReason?: string | null): Promise<void> => {
    await retireAssumption(assumptionId, changeReason)
    await refreshAfterWrite()
  }

  return {
    clients,
    selectedClient,
    assumptions,
    catalog,
    history,
    loading,
    loaded,
    staleAfterWrite,
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
