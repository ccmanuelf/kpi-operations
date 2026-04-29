/**
 * Clipboard parser for Excel-style copy/paste into data grids.
 * Tab-separated paste payloads → typed row objects.
 */

export interface ParsedClipboard {
  rows: string[][]
  headers: string[]
  hasHeaders?: boolean
  totalRows?: number
  totalColumns?: number
  error?: string
}

export interface GridColumnDef {
  field?: string
  headerName?: string
  type?: string
}

export interface ColumnMapping {
  [clipIndex: number]: string
}

export interface MapColumnsResult {
  mapping: ColumnMapping
  unmappedClipboard: { index: number; header: string }[]
  unmappedGrid: string[]
}

export interface FieldRule {
  type?: 'number' | 'date' | 'time' | 'string'
  min?: number
  max?: number
  pattern?: string
}

export interface EntrySchema {
  required?: string[]
  fields?: Record<string, FieldRule>
}

export interface ValidationResult {
  validRows: GridRow[]
  invalidRows: { row: GridRow; rowIndex: number; errors: string[] }[]
  isValid: boolean
  totalValid: number
  totalInvalid: number
}

export type GridRow = Record<string, unknown> & {
  _rowIndex?: number
  _isNew?: boolean
  _hasChanges?: boolean
  _pastedRow?: boolean
}

export function parseClipboardData(clipboardText: string): ParsedClipboard {
  if (!clipboardText || typeof clipboardText !== 'string') {
    return { rows: [], headers: [], error: 'No data in clipboard' }
  }

  const lines = clipboardText.trim().split(/\r?\n/)
  if (lines.length === 0) {
    return { rows: [], headers: [], error: 'No data found' }
  }

  const parsedRows = lines.map((line) => line.split('\t').map((cell) => cell.trim()))

  const firstRow = parsedRows[0]
  const isHeaderRow = firstRow.some((cell) => {
    const lower = cell.toLowerCase()
    return (
      lower.includes('date') ||
      lower.includes('id') ||
      lower.includes('name') ||
      lower.includes('quantity') ||
      lower.includes('units') ||
      lower.includes('hours') ||
      lower.includes('shift') ||
      lower.includes('product') ||
      lower === 'fecha' ||
      lower === 'turno' ||
      lower === 'producto'
    )
  })

  const headers = isHeaderRow ? parsedRows[0] : []
  const dataRows = isHeaderRow ? parsedRows.slice(1) : parsedRows

  return {
    rows: dataRows,
    headers,
    hasHeaders: isHeaderRow,
    totalRows: dataRows.length,
    totalColumns: dataRows[0]?.length || 0,
  }
}

export function mapColumnsToGrid(
  clipboardHeaders: string[],
  gridColumns: GridColumnDef[],
): MapColumnsResult {
  const mapping: ColumnMapping = {}
  const unmappedClipboard: { index: number; header: string }[] = []
  const unmappedGrid: string[] = []

  const gridColumnLookup: Record<string, string> = {}
  gridColumns.forEach((col) => {
    if (col.field && col.field !== 'actions') {
      const normalizedHeader = normalizeHeader(col.headerName || col.field)
      const normalizedField = normalizeHeader(col.field)
      gridColumnLookup[normalizedHeader] = col.field
      gridColumnLookup[normalizedField] = col.field
    }
  })

  clipboardHeaders.forEach((header, index) => {
    const normalized = normalizeHeader(header)
    const matchedField = gridColumnLookup[normalized]
    if (matchedField) {
      mapping[index] = matchedField
    } else {
      unmappedClipboard.push({ index, header })
    }
  })

  gridColumns.forEach((col) => {
    if (col.field && col.field !== 'actions') {
      const isMapped = Object.values(mapping).includes(col.field)
      if (!isMapped) {
        unmappedGrid.push(col.field)
      }
    }
  })

  return { mapping, unmappedClipboard, unmappedGrid }
}

function normalizeHeader(header: string): string {
  if (!header) return ''
  return header
    .toLowerCase()
    .replace(/[^a-z0-9]/g, '')
    .replace(/fecha/g, 'date')
    .replace(/turno/g, 'shift')
    .replace(/producto/g, 'product')
    .replace(/unidades/g, 'units')
    .replace(/cantidad/g, 'quantity')
    .replace(/horas/g, 'hours')
    .replace(/empleados/g, 'employees')
    .replace(/defectos/g, 'defects')
    .replace(/desperdicio/g, 'scrap')
}

export function convertToGridRows(
  rows: string[][],
  columnMapping: ColumnMapping,
  gridColumns: GridColumnDef[],
): GridRow[] {
  const columnTypes: Record<string, string> = {}
  gridColumns.forEach((col) => {
    if (col.field) {
      columnTypes[col.field] = col.type || 'text'
    }
  })

  return rows.map((row, rowIndex) => {
    const rowObject: GridRow = {
      _rowIndex: rowIndex,
      _isNew: true,
      _hasChanges: true,
      _pastedRow: true,
    }

    Object.entries(columnMapping).forEach(([clipIndex, gridField]) => {
      const rawValue = row[parseInt(clipIndex, 10)] || ''
      rowObject[gridField] = convertValue(rawValue, columnTypes[gridField], gridField)
    })

    return rowObject
  })
}

function convertValue(value: string, type: string | undefined, field: string): unknown {
  if (value === '' || value === null || value === undefined) {
    return type === 'numericColumn' ? 0 : ''
  }

  if (field?.includes('date') || type === 'date') {
    return parseDate(value)
  }

  if (type === 'numericColumn') {
    const num = parseFloat(value.replace(/,/g, ''))
    return isNaN(num) ? 0 : num
  }

  if (
    field?.includes('count') ||
    field?.includes('quantity') ||
    field?.includes('assigned') ||
    field?.includes('units')
  ) {
    const num = parseInt(value.replace(/,/g, ''), 10)
    return isNaN(num) ? 0 : num
  }

  if (field?.includes('hours') || field?.includes('time')) {
    const num = parseFloat(value.replace(/,/g, ''))
    return isNaN(num) ? 0 : num
  }

  return value
}

function parseDate(dateStr: string): string {
  if (!dateStr) return ''

  const isoMatch = dateStr.match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (isoMatch) {
    return dateStr.substring(0, 10)
  }

  const dateObj = new Date(dateStr)
  if (!isNaN(dateObj.getTime())) {
    return dateObj.toISOString().split('T')[0]
  }

  const dmyMatch = dateStr.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/)
  if (dmyMatch) {
    const [, day, month, year] = dmyMatch
    const d = parseInt(day, 10)
    const m = parseInt(month, 10)
    if (d > 12) {
      return `${year}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`
    }
    if (m > 12) {
      return `${year}-${String(d).padStart(2, '0')}-${String(m).padStart(2, '0')}`
    }
    return `${year}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`
  }

  return dateStr
}

export function validateRows(rows: GridRow[], schema: EntrySchema): ValidationResult {
  const validRows: GridRow[] = []
  const invalidRows: { row: GridRow; rowIndex: number; errors: string[] }[] = []

  rows.forEach((row, index) => {
    const errors: string[] = []

    if (schema.required) {
      schema.required.forEach((field) => {
        const value = row[field]
        if (value === undefined || value === null || value === '') {
          errors.push(`${field} is required`)
        }
      })
    }

    if (schema.fields) {
      Object.entries(schema.fields).forEach(([field, rules]) => {
        const value = row[field]

        if (rules.type === 'number' && value !== undefined) {
          if (typeof value !== 'number' || isNaN(value)) {
            errors.push(`${field} must be a number`)
          }
          if (rules.min !== undefined && typeof value === 'number' && value < rules.min) {
            errors.push(`${field} must be at least ${rules.min}`)
          }
          if (rules.max !== undefined && typeof value === 'number' && value > rules.max) {
            errors.push(`${field} must be at most ${rules.max}`)
          }
        }

        if (rules.type === 'date' && value) {
          if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
            errors.push(`${field} must be a valid date`)
          }
        }

        if (rules.pattern && value) {
          if (typeof value !== 'string' || !new RegExp(rules.pattern).test(value)) {
            errors.push(`${field} has invalid format`)
          }
        }
      })
    }

    if (errors.length > 0) {
      invalidRows.push({ row, rowIndex: index, errors })
    } else {
      validRows.push(row)
    }
  })

  return {
    validRows,
    invalidRows,
    isValid: invalidRows.length === 0,
    totalValid: validRows.length,
    totalInvalid: invalidRows.length,
  }
}

export const entrySchemas: Record<string, EntrySchema> = {
  production: {
    required: ['production_date', 'units_produced'],
    fields: {
      production_date: { type: 'date' },
      units_produced: { type: 'number', min: 0 },
      run_time_hours: { type: 'number', min: 0, max: 24 },
      employees_assigned: { type: 'number', min: 1 },
      defect_count: { type: 'number', min: 0 },
      scrap_count: { type: 'number', min: 0 },
    },
  },
  quality: {
    required: ['shift_date', 'units_inspected'],
    fields: {
      shift_date: { type: 'date' },
      units_inspected: { type: 'number', min: 0 },
      units_passed: { type: 'number', min: 0 },
      units_defective: { type: 'number', min: 0 },
      units_reworked: { type: 'number', min: 0 },
      units_scrapped: { type: 'number', min: 0 },
    },
  },
  attendance: {
    required: ['attendance_date'],
    fields: {
      attendance_date: { type: 'date' },
      scheduled_hours: { type: 'number', min: 0, max: 24 },
      worked_hours: { type: 'number', min: 0, max: 24 },
    },
  },
  downtime: {
    required: ['shift_date', 'downtime_minutes'],
    fields: {
      shift_date: { type: 'date' },
      downtime_minutes: { type: 'number', min: 0 },
      start_time: { type: 'time' },
      end_time: { type: 'time' },
    },
  },
  hold: {
    required: ['hold_date', 'work_order_id'],
    fields: {
      hold_date: { type: 'date' },
      quantity_held: { type: 'number', min: 0 },
    },
  },
}

export async function readClipboard(): Promise<string> {
  try {
    if (navigator.clipboard && navigator.clipboard.readText) {
      return await navigator.clipboard.readText()
    }

    return new Promise((resolve) => {
      const textArea = document.createElement('textarea')
      textArea.style.position = 'fixed'
      textArea.style.left = '-9999px'
      document.body.appendChild(textArea)
      textArea.focus()

      setTimeout(() => {
        document.execCommand('paste')
        const text = textArea.value
        document.body.removeChild(textArea)
        resolve(text)
      }, 100)
    })
  } catch (error) {
    // eslint-disable-next-line no-console
    console.error('Failed to read clipboard:', error)
    throw new Error('Unable to read clipboard. Please ensure clipboard access is allowed.')
  }
}

export function generateSampleData(entryType: string): string {
  const today = new Date().toISOString().split('T')[0]

  const samples: Record<string, string[]> = {
    production: [
      'Date\tProduct\tShift\tWork Order\tUnits Produced\tRuntime Hours\tEmployees\tDefects\tScrap',
      `${today}\tPROD-001\t1\tWO-2025-001\t500\t8.0\t5\t3\t1`,
      `${today}\tPROD-002\t1\tWO-2025-002\t450\t7.5\t4\t2\t0`,
    ],
    quality: [
      'Date\tWork Order\tStage\tInspected\tPassed\tDefective\tReworked\tScrapped',
      `${today}\tWO-2025-001\tFinal\t500\t485\t15\t10\t2`,
      `${today}\tWO-2025-002\tIn-Process\t450\t440\t10\t8\t1`,
    ],
    attendance: [
      'Date\tEmployee ID\tEmployee Name\tScheduled Hours\tWorked Hours\tAbsence Type',
      `${today}\tEMP-001\tJuan Garcia\t8.0\t8.0\t`,
      `${today}\tEMP-002\tMaria Lopez\t8.0\t0.0\tSick Leave`,
    ],
  }

  return (samples[entryType] || samples.production).join('\n')
}

export default {
  parseClipboardData,
  mapColumnsToGrid,
  convertToGridRows,
  validateRows,
  readClipboard,
  entrySchemas,
  generateSampleData,
}
