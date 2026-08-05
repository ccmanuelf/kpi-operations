/**
 * Pure helpers backing the WO detail drawer's delay-classification
 * section (role gating, payload shaping). Kept separate from
 * constants/delayTaxonomy.ts (a lean mirror of the backend enum module)
 * per the script-setup testing convention: WorkOrderDetailDrawer.vue is
 * a plain <script setup> SFC, so its logic lives here where it's
 * directly unit-testable.
 *
 * Role set mirrors backend/orm/user.py::SUPERVISORY_ROLES (admin,
 * poweruser, leader, supervisor) — the same set the backend enforces
 * server-side in crud/work_order.py::update_work_order (403 otherwise).
 * This is UI-only gating (defense in depth, not the source of truth).
 */

export const DELAY_SUPERVISORY_ROLES: string[] = ['admin', 'poweruser', 'leader', 'supervisor']

export const canEditDelayClassification = (role: string | null | undefined): boolean =>
  DELAY_SUPERVISORY_ROLES.includes(role ?? '')

// Only late work orders are eligible for classification (backend 422s
// otherwise) — the section renders iff this is true.
export interface DelayVisibilityRow {
  is_late?: boolean
}

export const isDelaySectionVisible = (row: DelayVisibilityRow | null | undefined): boolean =>
  Boolean(row?.is_late)

export interface DelayClassificationForm {
  classification: string | null
  reason: string | null
  note: string
}

export interface DelayClassificationPayload {
  delay_classification: string | null
  justified_delay_reason: string | null
  delay_classification_note: string | null
}

// Picking "Unclassified" submits classification: null, which the backend
// treats as an explicit clear (drops reason + note server-side); mirror
// that here so the payload is idempotent with the server's own rules.
export const buildDelayClassificationPayload = (
  form: DelayClassificationForm,
): DelayClassificationPayload => ({
  delay_classification: form.classification,
  justified_delay_reason: form.classification === 'justified' ? form.reason : null,
  delay_classification_note: form.classification === null ? null : form.note || null,
})
