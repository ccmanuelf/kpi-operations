/**
 * CSV Validation Utilities
 * Validates production entry data from CSV uploads
 */

export const requiredColumns = [
  'production_date',
  'product_id',
  'shift_id',
  'units_produced',
  'run_time_hours',
  'employees_assigned'
]

export const optionalColumns = [
  'work_order_number',
  'defect_count',
  'scrap_count',
  'notes'
]

/**
 * Validate date format (YYYY-MM-DD)
 */
export const validateDate = (dateString) => {
  if (!dateString) return { valid: false, error: 'Date is required' }

  const dateRegex = /^\d{4}-\d{2}-\d{2}$/
  if (!dateRegex.test(dateString)) {
    return { valid: false, error: 'Invalid date format (use YYYY-MM-DD)' }
  }

  const date = new Date(dateString)
  if (isNaN(date.getTime())) {
    return { valid: false, error: 'Invalid date value' }
  }

  return { valid: true, value: dateString }
}

/**
 * Validate positive integer
 */
export const validatePositiveInteger = (value, fieldName, minValue = 0) => {
  if (!value && value !== 0) {
    return { valid: false, error: `${fieldName} is required` }
  }

  const numValue = parseInt(value)
  if (isNaN(numValue)) {
    return { valid: false, error: `${fieldName} must be a number` }
  }

  if (numValue < minValue) {
    return { valid: false, error: `${fieldName} must be at least ${minValue}` }
  }

  return { valid: true, value: numValue }
}

/**
 * Validate positive decimal
 */
export const validatePositiveDecimal = (value, fieldName, minValue = 0) => {
  if (!value && value !== 0) {
    return { valid: false, error: `${fieldName} is required` }
  }

  const numValue = parseFloat(value)
  if (isNaN(numValue)) {
    return { valid: false, error: `${fieldName} must be a number` }
  }

  if (numValue <= minValue) {
    return { valid: false, error: `${fieldName} must be greater than ${minValue}` }
  }

  return { valid: true, value: numValue }
}

/**
 * Validate a complete production entry row
 */
export const validateProductionEntry = (row, rowIndex) => {
  const errors = []
  const validatedData = {}

  // Validate required fields
  const dateValidation = validateDate(row.production_date)
  if (!dateValidation.valid) {
    errors.push(dateValidation.error)
  } else {
    validatedData.production_date = dateValidation.value
  }

  const productIdValidation = validatePositiveInteger(row.product_id, 'Product ID', 1)
  if (!productIdValidation.valid) {
    errors.push(productIdValidation.error)
  } else {
    validatedData.product_id = productIdValidation.value
  }

  const shiftIdValidation = validatePositiveInteger(row.shift_id, 'Shift ID', 1)
  if (!shiftIdValidation.valid) {
    errors.push(shiftIdValidation.error)
  } else {
    validatedData.shift_id = shiftIdValidation.value
  }

  const unitsValidation = validatePositiveInteger(row.units_produced, 'Units Produced', 0)
  if (!unitsValidation.valid) {
    errors.push(unitsValidation.error)
  } else {
    validatedData.units_produced = unitsValidation.value
  }

  const runtimeValidation = validatePositiveDecimal(row.run_time_hours, 'Runtime Hours', 0)
  if (!runtimeValidation.valid) {
    errors.push(runtimeValidation.error)
  } else {
    validatedData.run_time_hours = runtimeValidation.value
  }

  const employeesValidation = validatePositiveInteger(row.employees_assigned, 'Employees', 1)
  if (!employeesValidation.valid) {
    errors.push(employeesValidation.error)
  } else {
    validatedData.employees_assigned = employeesValidation.value
  }

  // Validate optional fields with defaults
  validatedData.defect_count = parseInt(row.defect_count || 0)
  validatedData.scrap_count = parseInt(row.scrap_count || 0)
  validatedData.work_order_number = row.work_order_number || ''
  validatedData.notes = row.notes || ''

  return {
    valid: errors.length === 0,
    errors,
    data: validatedData,
    rowIndex
  }
}

/**
 * Calculate mock efficiency for preview
 */
export const calculateMockEfficiency = (unitsProduced, runTimeHours) => {
  if (!runTimeHours || runTimeHours <= 0) return 0

  // Mock calculation: assume 0.05 hours per unit as standard
  const standardHours = unitsProduced * 0.05
  const efficiency = (standardHours / runTimeHours) * 100

  return Math.min(efficiency, 100).toFixed(2) // Cap at 100%
}

/**
 * Calculate mock performance for preview
 */
export const calculateMockPerformance = (unitsProduced, runTimeHours, employeesAssigned) => {
  if (!runTimeHours || runTimeHours <= 0 || !employeesAssigned) return 0

  // Mock calculation: units per employee-hour
  const unitsPerEmployeeHour = unitsProduced / (runTimeHours * employeesAssigned)
  const standardRate = 20 // Assume 20 units per employee-hour as standard
  const performance = (unitsPerEmployeeHour / standardRate) * 100

  return Math.min(performance, 100).toFixed(2)
}

/**
 * Validate CSV headers
 */
export const validateHeaders = (headers) => {
  const missingColumns = requiredColumns.filter(col => !headers.includes(col))

  if (missingColumns.length > 0) {
    return {
      valid: false,
      error: `Missing required columns: ${missingColumns.join(', ')}`,
      missingColumns
    }
  }

  return { valid: true }
}
