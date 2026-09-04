/**
 * Composable for Part Opportunities form handling and CRUD.
 * Create/edit dialogs, validation rules, save/delete, CSV upload,
 * template download.
 */
import { ref, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import * as Papa from 'papaparse'
import api from '@/services/api'

export interface PartOpportunityFormData {
  part_number: string
  opportunities_per_unit: number
  part_description: string
  complexity: string
  client_id: string | number | null
  notes: string
  is_active: boolean
  part_opportunities_id?: string | number
}

export interface PartOpportunityRow extends PartOpportunityFormData {
  part_opportunities_id: string | number
  [key: string]: unknown
}

interface FormHandle {
  reset?: () => void
  validate?: () => Promise<{ valid: boolean }>
}

type ValidationRule = (_v: unknown) => true | string

interface ValidationRules {
  required: ValidationRule
  maxLength50: ValidationRule
  positive: ValidationRule
}

type SnackbarFn = (_message: string, _color: string) => void

const DEFAULT_FORM_DATA = (): PartOpportunityFormData => ({
  part_number: '',
  opportunities_per_unit: 10,
  part_description: '',
  complexity: '',
  client_id: null,
  notes: '',
  is_active: true,
})

/**
 * A whole positive integer, or null.
 *
 * NOT `Number.parseInt`, which silently truncates and coerces: it turns "5.9"
 * into 5, "12abc" into 12 and "1e2" into 1 — corrupting an import that then
 * SUCCEEDS. It also yields 0 and -3, which pass `Number.isFinite` and only
 * fail server-side, where the column requires > 0.
 */
export const parsePositiveInt = (raw: string | undefined): number | null => {
  const text = (raw ?? '').trim()
  if (!/^\d+$/.test(text)) return null
  const value = Number(text)
  return value > 0 ? value : null
}

export interface BulkImportRow {
  part_number: string
  client_id_fk: string
  opportunities_per_unit: number
  part_description: string | null
  part_category: string | null
  notes: string | null
}

/**
 * Parsed CSV rows -> the bulk-import payload, keeping only rows the endpoint
 * would accept.
 *
 * Exported so its tests exercise THIS function. The spec used to re-implement
 * the mapping and assert against its own copy, which cannot catch a change
 * here — and had already drifted from it.
 */
export const csvRowsToOpportunities = (
  rows: Record<string, string>[],
  clientId: string,
): BulkImportRow[] =>
  rows
    .map((row) => ({
      part_number: (row.part_number ?? '').trim(),
      client_id_fk: clientId,
      opportunities_per_unit: parsePositiveInt(row.opportunities_per_unit),
      part_description: row.part_description?.trim() || null,
      // `complexity` is what older templates emitted for this column.
      part_category: (row.part_category ?? row.complexity)?.trim() || null,
      notes: row.notes?.trim() || null,
    }))
    .filter((o): o is BulkImportRow => Boolean(o.part_number) && o.opportunities_per_unit !== null)

export function usePartOpportunitiesForms(
  selectedClient: Ref<string | number | null>,
  loadPartOpportunities: () => Promise<void>,
  showSnackbar: SnackbarFn,
) {
  const { t } = useI18n()

  const editDialog = ref(false)
  const uploadDialog = ref(false)
  const deleteDialog = ref(false)
  const isEditing = ref(false)
  const deleteTarget = ref<PartOpportunityRow | null>(null)

  const saving = ref(false)
  const uploading = ref(false)
  const deleting = ref(false)

  const form = ref<FormHandle | null>(null)
  const formValid = ref(false)
  const formData = ref<PartOpportunityFormData>(DEFAULT_FORM_DATA())

  const uploadFile = ref<File | null>(null)

  const complexityOptions: string[] = ['Simple', 'Standard', 'Complex', 'Very Complex']

  const rules: ValidationRules = {
    required: (v) => !!v || t('validation.required'),
    maxLength50: (v) =>
      !v ||
      (typeof v === 'string' && v.length <= 50) ||
      t('validation.maxLength', { max: 50 }),
    positive: (v) => (typeof v === 'number' && v > 0) || t('validation.positive'),
  }

  const openCreateDialog = (): void => {
    isEditing.value = false
    formData.value = {
      ...DEFAULT_FORM_DATA(),
      complexity: 'Standard',
      client_id: selectedClient.value,
    }
    editDialog.value = true
  }

  const openEditDialog = (item: PartOpportunityRow): void => {
    isEditing.value = true
    formData.value = { ...item }
    editDialog.value = true
  }

  const closeEditDialog = (): void => {
    editDialog.value = false
    form.value?.reset?.()
  }

  const savePartOpportunity = async (): Promise<void> => {
    if (!formValid.value) return

    saving.value = true
    try {
      if (isEditing.value && formData.value.part_opportunities_id) {
        await api.put(
          `/part-opportunities/${formData.value.part_opportunities_id}`,
          formData.value,
        )
        showSnackbar(t('success.updated'), 'success')
      } else {
        await api.post('/part-opportunities', formData.value)
        showSnackbar(t('success.saved'), 'success')
      }
      closeEditDialog()
      await loadPartOpportunities()
    } catch (error) {
      const ax = error as { response?: { data?: { detail?: string } } }
      showSnackbar(ax?.response?.data?.detail || t('errors.general'), 'error')
    } finally {
      saving.value = false
    }
  }

  const confirmDelete = (item: PartOpportunityRow): void => {
    deleteTarget.value = item
    deleteDialog.value = true
  }

  const deletePartOpportunity = async (): Promise<void> => {
    if (!deleteTarget.value) return

    deleting.value = true
    try {
      await api.delete(`/part-opportunities/${deleteTarget.value.part_opportunities_id}`)
      showSnackbar(t('success.deleted'), 'success')
      deleteDialog.value = false
      await loadPartOpportunities()
    } catch (error) {
      const ax = error as { response?: { data?: { detail?: string } } }
      showSnackbar(ax?.response?.data?.detail || t('errors.general'), 'error')
    } finally {
      deleting.value = false
    }
  }

  const openUploadDialog = (): void => {
    uploadFile.value = null
    uploadDialog.value = true
  }

  const closeUploadDialog = (): void => {
    uploadDialog.value = false
    uploadFile.value = null
  }

  const uploadCSV = async (): Promise<void> => {
    if (!uploadFile.value) return

    // POST /api/part-opportunities/bulk-import takes JSON — a
    // { opportunities: PartOpportunityCreate[] } body — not multipart. This
    // used to post a file to `/part-opportunities/upload`, a path with no
    // server route, so every upload 404'd and surfaced as the generic
    // t('csv.error') toast with nothing to act on. There is no file-upload
    // endpoint for this resource; the CSV is parsed here and sent as rows.
    if (!selectedClient.value) {
      showSnackbar(t('csv.selectClientFirst'), 'error')
      return
    }

    uploading.value = true
    try {
      const text = await uploadFile.value.text()
      const parsed = Papa.parse<Record<string, string>>(text, {
        header: true,
        skipEmptyLines: true,
      })

      const opportunities = csvRowsToOpportunities(parsed.data, String(selectedClient.value))

      // Rows dropped here never reach the server, so they are absent from its
      // failure_count. Reporting only what the server saw would tell the user
      // "70 imported" about a 100-row file and never mention the other 30.
      const skipped = parsed.data.length - opportunities.length

      if (opportunities.length === 0) {
        showSnackbar(t('csv.noValidRows'), 'error')
        return
      }

      const res = await api.post('/part-opportunities/bulk-import', { opportunities })
      const { success_count: created = 0, failure_count: failed = 0, errors = [] } = res.data ?? {}

      const skippedNote = skipped > 0 ? ` ${t('csv.skippedInvalidRows', { skipped })}` : ''

      if (failed > 0 || skipped > 0) {
        // Report the partial outcome rather than a bare success: the endpoint
        // imports row by row and returns what it could not take, and rows we
        // rejected locally never reached it at all.
        showSnackbar(
          t('csv.partialSuccess', { count: created, failed }) +
            skippedNote +
            (errors[0] ? ` — ${errors[0]}` : ''),
          'warning'
        )
      } else {
        showSnackbar(t('csv.success', { count: created }), 'success')
      }
      closeUploadDialog()
      await loadPartOpportunities()
    } catch (error) {
      const ax = error as { response?: { data?: { detail?: string } } }
      showSnackbar(ax?.response?.data?.detail || t('csv.error'), 'error')
    } finally {
      uploading.value = false
    }
  }

  const downloadTemplate = (): void => {
    // `part_category`, not `complexity`: the schema has no complexity field,
    // so the old template taught a column the import silently dropped.
    const csvHeaders = [
      'part_number',
      'opportunities_per_unit',
      'part_description',
      'part_category',
      'notes',
    ]
    const example = ['PART-001', '15', 'Standard T-Shirt', 'Standard', 'Basic garment']
    const csv = [csvHeaders.join(','), example.join(',')].join('\n')

    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'part_opportunities_template.csv'
    a.click()
    URL.revokeObjectURL(url)

    showSnackbar(t('success.downloaded'), 'success')
  }

  return {
    editDialog,
    uploadDialog,
    deleteDialog,
    isEditing,
    deleteTarget,
    saving,
    uploading,
    deleting,
    form,
    formValid,
    formData,
    uploadFile,
    complexityOptions,
    rules,
    openCreateDialog,
    openEditDialog,
    closeEditDialog,
    savePartOpportunity,
    confirmDelete,
    deletePartOpportunity,
    openUploadDialog,
    closeUploadDialog,
    uploadCSV,
    downloadTemplate,
  }
}
