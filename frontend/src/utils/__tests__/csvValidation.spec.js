/**
 * Unit tests for CSV Validation Utilities
 * Tests validation functions for production CSV uploads
 */
import { describe, it, expect } from 'vitest'
import {
  requiredColumns,
  optionalColumns,
  validateDate,
  validatePositiveInteger,
  validatePositiveDecimal,
  validateProductionEntry,
  calculateMockEfficiency,
  calculateMockPerformance,
  validateHeaders
} from '../csvValidation'

describe('CSV Validation', () => {
  describe('Constants', () => {
    it('defines required columns', () => {
      expect(requiredColumns).toContain('production_date')
      expect(requiredColumns).toContain('product_id')
      expect(requiredColumns).toContain('shift_id')
      expect(requiredColumns).toContain('units_produced')
      expect(requiredColumns).toContain('run_time_hours')
      expect(requiredColumns).toContain('employees_assigned')
      expect(requiredColumns).toHaveLength(6)
    })

    it('defines optional columns', () => {
      expect(optionalColumns).toContain('work_order_number')
      expect(optionalColumns).toContain('defect_count')
      expect(optionalColumns).toContain('scrap_count')
      expect(optionalColumns).toContain('notes')
    })
  })

  describe('validateDate', () => {
    it('validates correct date format', () => {
      const result = validateDate('2024-01-15')

      expect(result.valid).toBe(true)
      expect(result.value).toBe('2024-01-15')
    })

    it('rejects empty date', () => {
      const result = validateDate('')

      expect(result.valid).toBe(false)
      expect(result.error).toBe('Date is required')
    })

    it('rejects null date', () => {
      const result = validateDate(null)

      expect(result.valid).toBe(false)
      expect(result.error).toBe('Date is required')
    })

    it('rejects invalid format', () => {
      const result = validateDate('01/15/2024')

      expect(result.valid).toBe(false)
      expect(result.error).toBe('Invalid date format (use YYYY-MM-DD)')
    })

    it('rejects invalid date value', () => {
      const result = validateDate('2024-13-45')

      expect(result.valid).toBe(false)
      expect(result.error).toBe('Invalid date value')
    })

    it('validates edge dates', () => {
      expect(validateDate('2024-02-29').valid).toBe(true) // Leap year
      expect(validateDate('2024-12-31').valid).toBe(true)
      expect(validateDate('2024-01-01').valid).toBe(true)
    })
  })

  describe('validatePositiveInteger', () => {
    it('validates positive integer', () => {
      const result = validatePositiveInteger(10, 'Count')

      expect(result.valid).toBe(true)
      expect(result.value).toBe(10)
    })

    it('validates zero when minValue is 0', () => {
      const result = validatePositiveInteger(0, 'Count', 0)

      expect(result.valid).toBe(true)
      expect(result.value).toBe(0)
    })

    it('rejects empty value', () => {
      const result = validatePositiveInteger(null, 'Count')

      expect(result.valid).toBe(false)
      expect(result.error).toBe('Count is required')
    })

    it('rejects non-numeric value', () => {
      const result = validatePositiveInteger('abc', 'Count')

      expect(result.valid).toBe(false)
      expect(result.error).toBe('Count must be a number')
    })

    it('rejects value below minValue', () => {
      const result = validatePositiveInteger(0, 'Count', 1)

      expect(result.valid).toBe(false)
      expect(result.error).toBe('Count must be at least 1')
    })

    it('parses string numbers', () => {
      const result = validatePositiveInteger('42', 'Count')

      expect(result.valid).toBe(true)
      expect(result.value).toBe(42)
    })
  })

  describe('validatePositiveDecimal', () => {
    it('validates positive decimal', () => {
      const result = validatePositiveDecimal(8.5, 'Hours')

      expect(result.valid).toBe(true)
      expect(result.value).toBe(8.5)
    })

    it('rejects empty value', () => {
      const result = validatePositiveDecimal(null, 'Hours')

      expect(result.valid).toBe(false)
      expect(result.error).toBe('Hours is required')
    })

    it('rejects non-numeric value', () => {
      const result = validatePositiveDecimal('abc', 'Hours')

      expect(result.valid).toBe(false)
      expect(result.error).toBe('Hours must be a number')
    })

    it('rejects value at or below minValue', () => {
      const result = validatePositiveDecimal(0, 'Hours', 0)

      expect(result.valid).toBe(false)
      expect(result.error).toBe('Hours must be greater than 0')
    })

    it('parses string decimals', () => {
      const result = validatePositiveDecimal('3.14', 'Value')

      expect(result.valid).toBe(true)
      expect(result.value).toBeCloseTo(3.14)
    })
  })

  describe('validateProductionEntry', () => {
    const validRow = {
      production_date: '2024-01-15',
      product_id: 1,
      shift_id: 1,
      units_produced: 100,
      run_time_hours: 8,
      employees_assigned: 5
    }

    it('validates complete valid row', () => {
      const result = validateProductionEntry(validRow, 0)

      expect(result.valid).toBe(true)
      expect(result.errors).toHaveLength(0)
      expect(result.data.production_date).toBe('2024-01-15')
      expect(result.data.units_produced).toBe(100)
    })

    it('returns row index', () => {
      const result = validateProductionEntry(validRow, 5)

      expect(result.rowIndex).toBe(5)
    })

    it('collects multiple errors', () => {
      const invalidRow = {
        production_date: 'bad-date',
        product_id: 0,
        shift_id: 'abc',
        units_produced: -10,
        run_time_hours: 0,
        employees_assigned: null
      }

      const result = validateProductionEntry(invalidRow, 0)

      expect(result.valid).toBe(false)
      expect(result.errors.length).toBeGreaterThan(0)
    })

    it('handles optional fields with defaults', () => {
      const result = validateProductionEntry(validRow, 0)

      expect(result.data.defect_count).toBe(0)
      expect(result.data.scrap_count).toBe(0)
      expect(result.data.work_order_number).toBe('')
      expect(result.data.notes).toBe('')
    })

    it('preserves optional field values', () => {
      const rowWithOptional = {
        ...validRow,
        defect_count: 5,
        scrap_count: 2,
        work_order_number: 'WO-123',
        notes: 'Test note'
      }

      const result = validateProductionEntry(rowWithOptional, 0)

      expect(result.data.defect_count).toBe(5)
      expect(result.data.scrap_count).toBe(2)
      expect(result.data.work_order_number).toBe('WO-123')
      expect(result.data.notes).toBe('Test note')
    })

    it('validates product_id minimum of 1', () => {
      const row = { ...validRow, product_id: 0 }
      const result = validateProductionEntry(row, 0)

      expect(result.valid).toBe(false)
      expect(result.errors.some(e => e.includes('Product ID'))).toBe(true)
    })

    it('validates shift_id minimum of 1', () => {
      const row = { ...validRow, shift_id: 0 }
      const result = validateProductionEntry(row, 0)

      expect(result.valid).toBe(false)
      expect(result.errors.some(e => e.includes('Shift ID'))).toBe(true)
    })

    it('validates employees_assigned minimum of 1', () => {
      const row = { ...validRow, employees_assigned: 0 }
      const result = validateProductionEntry(row, 0)

      expect(result.valid).toBe(false)
      expect(result.errors.some(e => e.includes('Employees'))).toBe(true)
    })
  })

  describe('calculateMockEfficiency', () => {
    it('calculates efficiency based on standard hours', () => {
      // 100 units * 0.05 hours/unit = 5 standard hours
      // 5 / 8 actual hours = 62.5%
      const result = calculateMockEfficiency(100, 8)

      expect(result).toBe('62.50')
    })

    it('returns 0 for zero runtime', () => {
      const result = calculateMockEfficiency(100, 0)

      expect(result).toBe(0)
    })

    it('returns 0 for negative runtime', () => {
      const result = calculateMockEfficiency(100, -5)

      expect(result).toBe(0)
    })

    it('caps efficiency at 100%', () => {
      // If actual time is much less than standard, cap at 100
      const result = calculateMockEfficiency(1000, 1)

      expect(parseFloat(result)).toBe(100)
    })

    it('handles zero units', () => {
      const result = calculateMockEfficiency(0, 8)

      expect(result).toBe('0.00')
    })
  })

  describe('calculateMockPerformance', () => {
    it('calculates performance based on units per employee-hour', () => {
      // 200 units / (8 hours * 5 employees) = 5 units/employee-hour
      // 5 / 20 standard = 25%
      const result = calculateMockPerformance(200, 8, 5)

      expect(result).toBe('25.00')
    })

    it('returns 0 for zero runtime', () => {
      const result = calculateMockPerformance(100, 0, 5)

      expect(result).toBe(0)
    })

    it('returns 0 for zero employees', () => {
      const result = calculateMockPerformance(100, 8, 0)

      expect(result).toBe(0)
    })

    it('returns 0 for null employees', () => {
      const result = calculateMockPerformance(100, 8, null)

      expect(result).toBe(0)
    })

    it('caps performance at 100%', () => {
      // Very high output would exceed 100%
      const result = calculateMockPerformance(10000, 1, 1)

      expect(parseFloat(result)).toBe(100)
    })
  })

  describe('validateHeaders', () => {
    it('validates complete headers', () => {
      const headers = [
        'production_date',
        'product_id',
        'shift_id',
        'units_produced',
        'run_time_hours',
        'employees_assigned',
        'defect_count'
      ]

      const result = validateHeaders(headers)

      expect(result.valid).toBe(true)
    })

    it('reports missing columns', () => {
      const headers = ['production_date', 'product_id']

      const result = validateHeaders(headers)

      expect(result.valid).toBe(false)
      expect(result.missingColumns).toContain('shift_id')
      expect(result.missingColumns).toContain('units_produced')
      expect(result.missingColumns).toContain('run_time_hours')
      expect(result.missingColumns).toContain('employees_assigned')
      expect(result.error).toContain('Missing required columns')
    })

    it('handles empty headers', () => {
      const result = validateHeaders([])

      expect(result.valid).toBe(false)
      expect(result.missingColumns).toHaveLength(6)
    })

    it('ignores extra columns', () => {
      const headers = [
        'production_date',
        'product_id',
        'shift_id',
        'units_produced',
        'run_time_hours',
        'employees_assigned',
        'extra_column_1',
        'extra_column_2'
      ]

      const result = validateHeaders(headers)

      expect(result.valid).toBe(true)
    })
  })
})
