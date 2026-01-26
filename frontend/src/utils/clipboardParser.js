/**
 * Clipboard Parser Utility for Excel Copy/Paste
 * Phase 7.1: Excel Copy/Paste into Data Grids
 *
 * Handles parsing of tab-separated values from Excel clipboard
 * and validates data against schema definitions.
 */

/**
 * Parse clipboard text (tab-separated values from Excel)
 * @param {string} clipboardText - Raw text from clipboard
 * @returns {Object} Parsed data with rows and headers
 */
export function parseClipboardData(clipboardText) {
  if (!clipboardText || typeof clipboardText !== 'string') {
    return { rows: [], headers: [], error: 'No data in clipboard' }
  }

  // Split by newlines (handle both \r\n and \n)
  const lines = clipboardText.trim().split(/\r?\n/)

  if (lines.length === 0) {
    return { rows: [], headers: [], error: 'No data found' }
  }

  // Parse each line into columns (tab-separated)
  const parsedRows = lines.map(line => {
    // Split by tab, but preserve empty cells
    return line.split('\t').map(cell => cell.trim())
  })

  // Determine if first row is headers (heuristic: check for common header patterns)
  const firstRow = parsedRows[0]
  const isHeaderRow = firstRow.some(cell => {
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
    totalColumns: dataRows[0]?.length || 0
  }
}

/**
 * Map clipboard columns to grid columns
 * @param {Array} clipboardHeaders - Headers from clipboard
 * @param {Array} gridColumns - Column definitions from grid
 * @returns {Object} Column mapping and unmapped columns
 */
export function mapColumnsToGrid(clipboardHeaders, gridColumns) {
  const mapping = {}
  const unmappedClipboard = []
  const unmappedGrid = []

  // Create normalized lookup for grid columns
  const gridColumnLookup = {}
  gridColumns.forEach(col => {
    if (col.field && col.field !== 'actions') {
      const normalizedHeader = normalizeHeader(col.headerName || col.field)
      const normalizedField = normalizeHeader(col.field)
      gridColumnLookup[normalizedHeader] = col.field
      gridColumnLookup[normalizedField] = col.field
    }
  })

  // Map clipboard headers to grid fields
  clipboardHeaders.forEach((header, index) => {
    const normalized = normalizeHeader(header)
    const matchedField = gridColumnLookup[normalized]

    if (matchedField) {
      mapping[index] = matchedField
    } else {
      unmappedClipboard.push({ index, header })
    }
  })

  // Find grid columns that weren't mapped
  gridColumns.forEach(col => {
    if (col.field && col.field !== 'actions') {
      const isMapped = Object.values(mapping).includes(col.field)
      if (!isMapped) {
        unmappedGrid.push(col.field)
      }
    }
  })

  return { mapping, unmappedClipboard, unmappedGrid }
}

/**
 * Normalize header string for matching
 * @param {string} header - Header text
 * @returns {string} Normalized header
 */
function normalizeHeader(header) {
  if (!header) return ''
  return header
    .toLowerCase()
    .replace(/[^a-z0-9]/g, '') // Remove special chars
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

/**
 * Convert parsed rows to grid-compatible objects
 * @param {Array} rows - Parsed data rows
 * @param {Object} columnMapping - Index to field mapping
 * @param {Array} gridColumns - Grid column definitions
 * @returns {Array} Array of row objects
 */
export function convertToGridRows(rows, columnMapping, gridColumns) {
  const columnTypes = {}
  gridColumns.forEach(col => {
    if (col.field) {
      columnTypes[col.field] = col.type || 'text'
    }
  })

  return rows.map((row, rowIndex) => {
    const rowObject = {
      _rowIndex: rowIndex,
      _isNew: true,
      _hasChanges: true,
      _pastedRow: true
    }

    Object.entries(columnMapping).forEach(([clipIndex, gridField]) => {
      const rawValue = row[parseInt(clipIndex)] || ''
      rowObject[gridField] = convertValue(rawValue, columnTypes[gridField], gridField)
    })

    return rowObject
  })
}

/**
 * Convert string value to appropriate type
 * @param {string} value - Raw string value
 * @param {string} type - Target type
 * @param {string} field - Field name for context
 * @returns {*} Converted value
 */
function convertValue(value, type, field) {
  if (value === '' || value === null || value === undefined) {
    return type === 'numericColumn' ? 0 : ''
  }

  // Handle date fields
  if (field?.includes('date') || type === 'date') {
    return parseDate(value)
  }

  // Handle numeric fields
  if (type === 'numericColumn') {
    const num = parseFloat(value.replace(/,/g, ''))
    return isNaN(num) ? 0 : num
  }

  // Handle integer fields
  if (field?.includes('count') || field?.includes('quantity') || field?.includes('assigned') || field?.includes('units')) {
    const num = parseInt(value.replace(/,/g, ''), 10)
    return isNaN(num) ? 0 : num
  }

  // Handle hours (decimal)
  if (field?.includes('hours') || field?.includes('time')) {
    const num = parseFloat(value.replace(/,/g, ''))
    return isNaN(num) ? 0 : num
  }

  return value
}

/**
 * Parse date string to ISO format
 * @param {string} dateStr - Date string in various formats
 * @returns {string} ISO date string (YYYY-MM-DD)
 */
function parseDate(dateStr) {
  if (!dateStr) return ''

  // Try various date formats
  const formats = [
    // ISO format
    /^(\d{4})-(\d{2})-(\d{2})/,
    // US format MM/DD/YYYY
    /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/,
    // US format MM-DD-YYYY
    /^(\d{1,2})-(\d{1,2})-(\d{4})$/,
    // Mexican format DD/MM/YYYY
    /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/
  ]

  // Try ISO format first
  const isoMatch = dateStr.match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (isoMatch) {
    return dateStr.substring(0, 10)
  }

  // Try common formats
  const dateObj = new Date(dateStr)
  if (!isNaN(dateObj.getTime())) {
    return dateObj.toISOString().split('T')[0]
  }

  // Try manual parsing for DD/MM/YYYY (common in Mexico)
  const dmyMatch = dateStr.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/)
  if (dmyMatch) {
    const [, day, month, year] = dmyMatch
    const d = parseInt(day, 10)
    const m = parseInt(month, 10)
    // If day > 12, assume DD/MM/YYYY
    if (d > 12) {
      return `${year}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`
    }
    // If month > 12, assume MM/DD/YYYY
    if (m > 12) {
      return `${year}-${String(d).padStart(2, '0')}-${String(m).padStart(2, '0')}`
    }
    // Default to DD/MM/YYYY for Mexican users
    return `${year}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`
  }

  return dateStr // Return original if parsing fails
}

/**
 * Validate converted rows against schema
 * @param {Array} rows - Converted row objects
 * @param {Object} schema - Validation schema
 * @returns {Object} Validation results with valid/invalid rows
 */
export function validateRows(rows, schema) {
  const validRows = []
  const invalidRows = []

  rows.forEach((row, index) => {
    const errors = []

    // Check required fields
    if (schema.required) {
      schema.required.forEach(field => {
        const value = row[field]
        if (value === undefined || value === null || value === '') {
          errors.push(`${field} is required`)
        }
      })
    }

    // Check field validations
    if (schema.fields) {
      Object.entries(schema.fields).forEach(([field, rules]) => {
        const value = row[field]

        if (rules.type === 'number' && value !== undefined) {
          if (typeof value !== 'number' || isNaN(value)) {
            errors.push(`${field} must be a number`)
          }
          if (rules.min !== undefined && value < rules.min) {
            errors.push(`${field} must be at least ${rules.min}`)
          }
          if (rules.max !== undefined && value > rules.max) {
            errors.push(`${field} must be at most ${rules.max}`)
          }
        }

        if (rules.type === 'date' && value) {
          if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) {
            errors.push(`${field} must be a valid date`)
          }
        }

        if (rules.pattern && value) {
          if (!new RegExp(rules.pattern).test(value)) {
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
    totalInvalid: invalidRows.length
  }
}

/**
 * Schema definitions for different entry types
 */
export const entrySchemas = {
  production: {
    required: ['production_date', 'units_produced'],
    fields: {
      production_date: { type: 'date' },
      units_produced: { type: 'number', min: 0 },
      run_time_hours: { type: 'number', min: 0, max: 24 },
      employees_assigned: { type: 'number', min: 1 },
      defect_count: { type: 'number', min: 0 },
      scrap_count: { type: 'number', min: 0 }
    }
  },
  quality: {
    required: ['shift_date', 'units_inspected'],
    fields: {
      shift_date: { type: 'date' },
      units_inspected: { type: 'number', min: 0 },
      units_passed: { type: 'number', min: 0 },
      units_defective: { type: 'number', min: 0 },
      units_reworked: { type: 'number', min: 0 },
      units_scrapped: { type: 'number', min: 0 }
    }
  },
  attendance: {
    required: ['attendance_date'],
    fields: {
      attendance_date: { type: 'date' },
      scheduled_hours: { type: 'number', min: 0, max: 24 },
      worked_hours: { type: 'number', min: 0, max: 24 }
    }
  },
  downtime: {
    required: ['shift_date', 'downtime_minutes'],
    fields: {
      shift_date: { type: 'date' },
      downtime_minutes: { type: 'number', min: 0 },
      start_time: { type: 'time' },
      end_time: { type: 'time' }
    }
  },
  hold: {
    required: ['hold_date', 'work_order_id'],
    fields: {
      hold_date: { type: 'date' },
      quantity_held: { type: 'number', min: 0 }
    }
  }
}

/**
 * Read clipboard data from browser
 * @returns {Promise<string>} Clipboard text content
 */
export async function readClipboard() {
  try {
    // Modern clipboard API
    if (navigator.clipboard && navigator.clipboard.readText) {
      return await navigator.clipboard.readText()
    }

    // Fallback for older browsers
    return new Promise((resolve, reject) => {
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
    console.error('Failed to read clipboard:', error)
    throw new Error('Unable to read clipboard. Please ensure clipboard access is allowed.')
  }
}

/**
 * Generate sample data string for testing
 * @param {string} entryType - Type of entry (production, quality, etc.)
 * @returns {string} Tab-separated sample data
 */
export function generateSampleData(entryType) {
  const today = new Date().toISOString().split('T')[0]

  const samples = {
    production: [
      'Date\tProduct\tShift\tWork Order\tUnits Produced\tRuntime Hours\tEmployees\tDefects\tScrap',
      `${today}\tPROD-001\t1\tWO-2025-001\t500\t8.0\t5\t3\t1`,
      `${today}\tPROD-002\t1\tWO-2025-002\t450\t7.5\t4\t2\t0`
    ],
    quality: [
      'Date\tWork Order\tStage\tInspected\tPassed\tDefective\tReworked\tScrapped',
      `${today}\tWO-2025-001\tFinal\t500\t485\t15\t10\t2`,
      `${today}\tWO-2025-002\tIn-Process\t450\t440\t10\t8\t1`
    ],
    attendance: [
      'Date\tEmployee ID\tEmployee Name\tScheduled Hours\tWorked Hours\tAbsence Type',
      `${today}\tEMP-001\tJuan Garcia\t8.0\t8.0\t`,
      `${today}\tEMP-002\tMaria Lopez\t8.0\t0.0\tSick Leave`
    ]
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
  generateSampleData
}
