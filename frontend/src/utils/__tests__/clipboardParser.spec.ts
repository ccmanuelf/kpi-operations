/**
 * Unit tests for Clipboard Parser Utility
 * Phase 8.1: Testing clipboard parsing for Excel copy/paste functionality
 */
import { describe, it, expect } from 'vitest'
import {
  parseClipboardData,
  mapColumnsToGrid,
  convertToGridRows,
  validateRows,
  entrySchemas,
  generateSampleData
} from '../clipboardParser'

describe('Clipboard Parser', () => {
  describe('parseClipboardData', () => {
    it('parses tab-separated values correctly without headers', () => {
      // No header keywords, so both rows returned as data
      const clipboard = 'col1\tcol2\tcol3\nval1\tval2\tval3'
      const result = parseClipboardData(clipboard)

      expect(result.hasHeaders).toBe(false)
      expect(result.rows).toHaveLength(2)
      expect(result.rows[0]).toEqual(['col1', 'col2', 'col3'])
      expect(result.rows[1]).toEqual(['val1', 'val2', 'val3'])
    })

    it('detects header row with date keyword', () => {
      const clipboard = 'Date\tProduct\tQuantity\n2024-01-15\tPROD-001\t100'
      const result = parseClipboardData(clipboard)

      expect(result.hasHeaders).toBe(true)
      expect(result.headers).toEqual(['Date', 'Product', 'Quantity'])
      expect(result.rows).toHaveLength(1)
      expect(result.rows[0]).toEqual(['2024-01-15', 'PROD-001', '100'])
    })

    it('detects header row with Spanish keywords', () => {
      const clipboard = 'Fecha\tTurno\tProducto\n2024-01-15\t1\tPROD-001'
      const result = parseClipboardData(clipboard)

      expect(result.hasHeaders).toBe(true)
      expect(result.headers).toContain('Fecha')
    })

    it('handles Windows line endings (CRLF)', () => {
      const clipboard = 'Date\tUnits\r\nValue1\tValue2\r\nValue3\tValue4'
      const result = parseClipboardData(clipboard)

      // Date is a header keyword
      expect(result.hasHeaders).toBe(true)
      expect(result.rows).toHaveLength(2)
      expect(result.rows[0]).toEqual(['Value1', 'Value2'])
      expect(result.rows[1]).toEqual(['Value3', 'Value4'])
    })

    it('handles Unix line endings (LF)', () => {
      const clipboard = 'Date\tQuantity\nValue1\tValue2\nValue3\tValue4'
      const result = parseClipboardData(clipboard)

      // Date is a header keyword
      expect(result.hasHeaders).toBe(true)
      expect(result.rows).toHaveLength(2)
    })

    it('returns error for empty clipboard', () => {
      const result = parseClipboardData('')

      expect(result.error).toBe('No data in clipboard')
      expect(result.rows).toHaveLength(0)
    })

    it('returns error for null input', () => {
      const result = parseClipboardData(null)

      expect(result.error).toBe('No data in clipboard')
    })

    it('returns error for non-string input', () => {
      const result = parseClipboardData(123)

      expect(result.error).toBe('No data in clipboard')
    })

    it('preserves empty cells', () => {
      const clipboard = 'Date\tName\tID\n1\t\t3'
      const result = parseClipboardData(clipboard)

      // 'Date', 'Name', 'ID' contain header keywords
      expect(result.hasHeaders).toBe(true)
      expect(result.rows[0]).toEqual(['1', '', '3'])
    })

    it('trims whitespace from cells', () => {
      const clipboard = 'Date\tQuantity\n  value1  \t  value2  '
      const result = parseClipboardData(clipboard)

      expect(result.rows[0]).toEqual(['value1', 'value2'])
    })

    it('reports total columns correctly', () => {
      const clipboard = 'Date\tUnits\tHours\tName\n1\t2\t3\t4'
      const result = parseClipboardData(clipboard)

      expect(result.totalColumns).toBe(4)
    })
  })

  describe('mapColumnsToGrid', () => {
    const mockGridColumns = [
      { field: 'production_date', headerName: 'Date' },
      { field: 'units_produced', headerName: 'Units Produced' },
      { field: 'run_time_hours', headerName: 'Runtime Hours' },
      { field: 'employees_assigned', headerName: 'Employees' },
      { field: 'actions', headerName: 'Actions' } // Should be ignored
    ]

    it('maps exact header matches', () => {
      const clipboardHeaders = ['Date', 'Units Produced', 'Runtime Hours']
      const result = mapColumnsToGrid(clipboardHeaders, mockGridColumns)

      expect(result.mapping[0]).toBe('production_date')
      expect(result.mapping[1]).toBe('units_produced')
      expect(result.mapping[2]).toBe('run_time_hours')
    })

    it('maps case-insensitive matches', () => {
      const clipboardHeaders = ['DATE', 'units produced', 'RUNTIME HOURS']
      const result = mapColumnsToGrid(clipboardHeaders, mockGridColumns)

      expect(result.mapping[0]).toBe('production_date')
      expect(result.mapping[1]).toBe('units_produced')
    })

    it('reports unmapped clipboard columns', () => {
      const clipboardHeaders = ['Date', 'Unknown Column', 'Units Produced']
      const result = mapColumnsToGrid(clipboardHeaders, mockGridColumns)

      expect(result.unmappedClipboard).toHaveLength(1)
      expect(result.unmappedClipboard[0].header).toBe('Unknown Column')
      expect(result.unmappedClipboard[0].index).toBe(1)
    })

    it('reports unmapped grid columns', () => {
      const clipboardHeaders = ['Date']
      const result = mapColumnsToGrid(clipboardHeaders, mockGridColumns)

      expect(result.unmappedGrid).toContain('units_produced')
      expect(result.unmappedGrid).toContain('run_time_hours')
      expect(result.unmappedGrid).toContain('employees_assigned')
    })

    it('ignores actions column', () => {
      const clipboardHeaders = ['Actions', 'Date']
      const result = mapColumnsToGrid(clipboardHeaders, mockGridColumns)

      expect(Object.values(result.mapping)).not.toContain('actions')
    })

    it('maps Spanish headers to English fields', () => {
      const clipboardHeaders = ['Fecha', 'Unidades', 'Horas']
      const result = mapColumnsToGrid(clipboardHeaders, mockGridColumns)

      // Fecha should normalize to 'date' and match production_date
      expect(result.mapping[0]).toBe('production_date')
    })
  })

  describe('convertToGridRows', () => {
    const mockGridColumns = [
      { field: 'production_date', type: 'date' },
      { field: 'units_produced', type: 'numericColumn' },
      { field: 'notes', type: 'text' }
    ]

    const columnMapping = {
      0: 'production_date',
      1: 'units_produced',
      2: 'notes'
    }

    it('converts rows to grid objects', () => {
      const rows = [['2024-01-15', '100', 'Test note']]
      const result = convertToGridRows(rows, columnMapping, mockGridColumns)

      expect(result).toHaveLength(1)
      expect(result[0].production_date).toBe('2024-01-15')
      expect(result[0].units_produced).toBe(100)
      expect(result[0].notes).toBe('Test note')
    })

    it('marks rows as new and changed', () => {
      const rows = [['2024-01-15', '100', '']]
      const result = convertToGridRows(rows, columnMapping, mockGridColumns)

      expect(result[0]._isNew).toBe(true)
      expect(result[0]._hasChanges).toBe(true)
      expect(result[0]._pastedRow).toBe(true)
    })

    it('adds row index metadata', () => {
      const rows = [['2024-01-15', '100', ''], ['2024-01-16', '200', '']]
      const result = convertToGridRows(rows, columnMapping, mockGridColumns)

      expect(result[0]._rowIndex).toBe(0)
      expect(result[1]._rowIndex).toBe(1)
    })

    it('converts numeric strings to numbers', () => {
      const rows = [['2024-01-15', '1,234', '']]
      const result = convertToGridRows(rows, columnMapping, mockGridColumns)

      expect(result[0].units_produced).toBe(1234)
    })

    it('handles empty numeric values', () => {
      const rows = [['2024-01-15', '', '']]
      const result = convertToGridRows(rows, columnMapping, mockGridColumns)

      expect(result[0].units_produced).toBe(0)
    })

    it('parses various date formats', () => {
      const rows = [
        ['2024-01-15', '100', ''],
        ['01/15/2024', '100', ''],
        ['15/01/2024', '100', '']
      ]
      const result = convertToGridRows(rows, columnMapping, mockGridColumns)

      expect(result[0].production_date).toBe('2024-01-15')
      // Additional date formats should be parseable
    })
  })

  describe('validateRows', () => {
    describe('production schema', () => {
      const schema = entrySchemas.production

      it('validates complete valid rows', () => {
        const rows = [{
          production_date: '2024-01-15',
          units_produced: 100,
          run_time_hours: 8,
          employees_assigned: 5,
          defect_count: 2,
          scrap_count: 1
        }]

        const result = validateRows(rows, schema)

        expect(result.isValid).toBe(true)
        expect(result.validRows).toHaveLength(1)
        expect(result.invalidRows).toHaveLength(0)
      })

      it('rejects missing required fields', () => {
        const rows = [{
          units_produced: 100 // Missing production_date
        }]

        const result = validateRows(rows, schema)

        expect(result.isValid).toBe(false)
        expect(result.invalidRows).toHaveLength(1)
        expect(result.invalidRows[0].errors).toContain('production_date is required')
      })

      it('rejects negative units', () => {
        const rows = [{
          production_date: '2024-01-15',
          units_produced: -10
        }]

        const result = validateRows(rows, schema)

        expect(result.isValid).toBe(false)
        expect(result.invalidRows[0].errors.some(e => e.includes('units_produced'))).toBe(true)
      })

      it('rejects invalid hours', () => {
        const rows = [{
          production_date: '2024-01-15',
          units_produced: 100,
          run_time_hours: 25 // More than 24
        }]

        const result = validateRows(rows, schema)

        expect(result.isValid).toBe(false)
        expect(result.invalidRows[0].errors.some(e => e.includes('run_time_hours'))).toBe(true)
      })

      it('rejects invalid date format', () => {
        const rows = [{
          production_date: 'not-a-date',
          units_produced: 100
        }]

        const result = validateRows(rows, schema)

        expect(result.isValid).toBe(false)
        expect(result.invalidRows[0].errors.some(e => e.includes('date'))).toBe(true)
      })
    })

    describe('quality schema', () => {
      const schema = entrySchemas.quality

      it('validates quality entries', () => {
        const rows = [{
          shift_date: '2024-01-15',
          units_inspected: 500,
          units_passed: 480,
          units_defective: 20
        }]

        const result = validateRows(rows, schema)

        expect(result.isValid).toBe(true)
      })
    })

    describe('attendance schema', () => {
      const schema = entrySchemas.attendance

      it('validates attendance entries', () => {
        const rows = [{
          attendance_date: '2024-01-15',
          scheduled_hours: 8,
          worked_hours: 8
        }]

        const result = validateRows(rows, schema)

        expect(result.isValid).toBe(true)
      })

      it('rejects hours over 24', () => {
        const rows = [{
          attendance_date: '2024-01-15',
          scheduled_hours: 25
        }]

        const result = validateRows(rows, schema)

        expect(result.isValid).toBe(false)
      })
    })

    it('collects multiple errors per row', () => {
      const rows = [{
        production_date: 'invalid',
        units_produced: -10,
        run_time_hours: 30
      }]

      const result = validateRows(rows, entrySchemas.production)

      expect(result.invalidRows[0].errors.length).toBeGreaterThan(1)
    })

    it('separates valid and invalid rows', () => {
      const rows = [
        { production_date: '2024-01-15', units_produced: 100 },
        { production_date: 'invalid', units_produced: -10 },
        { production_date: '2024-01-16', units_produced: 200 }
      ]

      const result = validateRows(rows, entrySchemas.production)

      expect(result.validRows).toHaveLength(2)
      expect(result.invalidRows).toHaveLength(1)
      expect(result.totalValid).toBe(2)
      expect(result.totalInvalid).toBe(1)
    })
  })

  describe('entrySchemas', () => {
    it('defines production schema', () => {
      expect(entrySchemas.production).toBeDefined()
      expect(entrySchemas.production.required).toContain('production_date')
      expect(entrySchemas.production.required).toContain('units_produced')
    })

    it('defines quality schema', () => {
      expect(entrySchemas.quality).toBeDefined()
      expect(entrySchemas.quality.required).toContain('shift_date')
      expect(entrySchemas.quality.required).toContain('units_inspected')
    })

    it('defines attendance schema', () => {
      expect(entrySchemas.attendance).toBeDefined()
      expect(entrySchemas.attendance.required).toContain('attendance_date')
    })

    it('defines downtime schema', () => {
      expect(entrySchemas.downtime).toBeDefined()
      expect(entrySchemas.downtime.required).toContain('shift_date')
      expect(entrySchemas.downtime.required).toContain('downtime_minutes')
    })

    it('defines hold schema', () => {
      expect(entrySchemas.hold).toBeDefined()
      expect(entrySchemas.hold.required).toContain('hold_date')
      expect(entrySchemas.hold.required).toContain('work_order_id')
    })
  })

  describe('generateSampleData', () => {
    it('generates production sample data', () => {
      const sample = generateSampleData('production')

      expect(sample).toContain('Date')
      expect(sample).toContain('Product')
      expect(sample).toContain('Units Produced')
      expect(sample.split('\n').length).toBeGreaterThan(1)
    })

    it('generates quality sample data', () => {
      const sample = generateSampleData('quality')

      expect(sample).toContain('Inspected')
      expect(sample).toContain('Passed')
      expect(sample).toContain('Defective')
    })

    it('generates attendance sample data', () => {
      const sample = generateSampleData('attendance')

      expect(sample).toContain('Employee')
      expect(sample).toContain('Scheduled Hours')
      expect(sample).toContain('Worked Hours')
    })

    it('falls back to production for unknown types', () => {
      const sample = generateSampleData('unknown')

      expect(sample).toContain('Units Produced')
    })

    it('uses current date in samples', () => {
      const today = new Date().toISOString().split('T')[0]
      const sample = generateSampleData('production')

      expect(sample).toContain(today)
    })
  })

  describe('Integration: Full paste workflow', () => {
    it('handles complete Excel paste workflow', () => {
      // Simulate Excel clipboard data
      const clipboard = `Date\tProduct\tUnits Produced\tRuntime Hours\tEmployees
2024-01-15\tPROD-001\t500\t8.0\t5
2024-01-16\tPROD-002\t450\t7.5\t4`

      const gridColumns = [
        { field: 'production_date', headerName: 'Date' },
        { field: 'product_id', headerName: 'Product' },
        { field: 'units_produced', headerName: 'Units Produced' },
        { field: 'run_time_hours', headerName: 'Runtime Hours' },
        { field: 'employees_assigned', headerName: 'Employees' }
      ]

      // Step 1: Parse clipboard
      const parsed = parseClipboardData(clipboard)
      expect(parsed.hasHeaders).toBe(true)
      expect(parsed.rows).toHaveLength(2)

      // Step 2: Map columns
      const columnMap = mapColumnsToGrid(parsed.headers, gridColumns)
      expect(Object.keys(columnMap.mapping).length).toBeGreaterThan(0)

      // Step 3: Convert to grid rows
      const gridRows = convertToGridRows(parsed.rows, columnMap.mapping, gridColumns)
      expect(gridRows).toHaveLength(2)
      expect(gridRows[0].units_produced).toBe(500)
      expect(gridRows[1].units_produced).toBe(450)

      // Step 4: Validate
      const validation = validateRows(gridRows, entrySchemas.production)
      expect(validation.isValid).toBe(true)
    })
  })
})
