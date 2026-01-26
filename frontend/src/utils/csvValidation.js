/**
 * CSV Validation Utilities
 * Validates production entry data from CSV uploads
 */

/**
 * Production Entry CSV Columns - ALIGNED WITH backend/routes/production.py
 */
export const requiredColumns = [
  'client_id',           // Multi-tenant isolation - REQUIRED
  'product_id',          // Product reference
  'shift_id',            // Shift reference
  'production_date',     // Format: YYYY-MM-DD
  'units_produced',      // Must be > 0
  'run_time_hours',      // Decimal hours
  'employees_assigned'   // Number of employees
]

export const optionalColumns = [
  'shift_date',          // Defaults to production_date if not provided
  'work_order_id',       // Work order reference (or work_order_number)
  'work_order_number',   // Alias for work_order_id
  'job_id',              // Job-level tracking
  'employees_present',   // Actual employees present
  'defect_count',        // Default: 0
  'scrap_count',         // Default: 0
  'rework_count',        // Default: 0
  'setup_time_hours',    // Setup time in hours
  'downtime_hours',      // Downtime in hours
  'maintenance_hours',   // Maintenance time in hours
  'ideal_cycle_time',    // Ideal hours per unit
  'notes'                // Free text notes
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
  // client_id is required
  if (!row.client_id || String(row.client_id).trim() === '') {
    errors.push('Client ID is required')
  } else {
    validatedData.client_id = String(row.client_id).trim()
  }

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
  validatedData.rework_count = parseInt(row.rework_count || 0)
  validatedData.work_order_id = row.work_order_id || row.work_order_number || ''
  validatedData.job_id = row.job_id || ''
  validatedData.employees_present = row.employees_present ? parseInt(row.employees_present) : null
  validatedData.setup_time_hours = row.setup_time_hours ? parseFloat(row.setup_time_hours) : null
  validatedData.downtime_hours = row.downtime_hours ? parseFloat(row.downtime_hours) : null
  validatedData.maintenance_hours = row.maintenance_hours ? parseFloat(row.maintenance_hours) : null
  validatedData.ideal_cycle_time = row.ideal_cycle_time ? parseFloat(row.ideal_cycle_time) : null
  validatedData.shift_date = row.shift_date || validatedData.production_date
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
