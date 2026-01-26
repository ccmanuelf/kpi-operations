/**
 * Unit tests for Client Config Store
 * Phase 8.1.5: Client config override inheritance
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

/**
 * Mock Client Config Store
 * Tests client-specific calculation parameter overrides
 */

// Default system configuration
const SYSTEM_DEFAULTS = {
  otd_mode: 'STANDARD',
  default_cycle_time_hours: 0.05,
  quality_target_ppm: 1000,
  efficiency_target_percent: 85,
  fpy_target_percent: 95,
  availability_target_percent: 90
}

// Client-specific overrides
const clientConfigs = new Map([
  ['client_1', {
    client_id: 'client_1',
    otd_mode: 'TRUE',
    default_cycle_time_hours: 0.08,
    quality_target_ppm: 500,
    efficiency_target_percent: 90
    // Note: fpy_target_percent and availability_target_percent not set, should inherit
  }],
  ['client_2', {
    client_id: 'client_2',
    otd_mode: 'BOTH',
    quality_target_ppm: 750
    // Most settings inherit from defaults
  }],
  ['client_3', {
    client_id: 'client_3'
    // Empty config - all settings should inherit from defaults
  }]
])

/**
 * Get effective configuration for a client
 * Merges client overrides with system defaults
 */
function getEffectiveConfig(clientId) {
  const clientConfig = clientConfigs.get(clientId) || {}
  return {
    ...SYSTEM_DEFAULTS,
    ...clientConfig,
    client_id: clientId
  }
}

/**
 * Check if a specific setting is inherited or overridden
 */
function isSettingInherited(clientId, settingKey) {
  const clientConfig = clientConfigs.get(clientId)
  if (!clientConfig) return true
  return !(settingKey in clientConfig) || clientConfig[settingKey] === undefined
}

/**
 * Validate OTD mode value
 */
function validateOtdMode(mode) {
  const validModes = ['STANDARD', 'TRUE', 'BOTH']
  return validModes.includes(mode)
}

/**
 * Calculate KPI with client-specific parameters
 */
function calculateEfficiency(unitsProduced, runTimeHours, clientId) {
  const config = getEffectiveConfig(clientId)
  const standardHours = unitsProduced * config.default_cycle_time_hours
  const efficiency = (standardHours / runTimeHours) * 100
  return Math.min(efficiency, 100).toFixed(2)
}

/**
 * Check if KPI meets client-specific target
 */
function checkKpiTarget(kpiType, value, clientId) {
  const config = getEffectiveConfig(clientId)
  const targets = {
    efficiency: config.efficiency_target_percent,
    fpy: config.fpy_target_percent,
    availability: config.availability_target_percent,
    quality_ppm: config.quality_target_ppm
  }

  const target = targets[kpiType]
  if (target === undefined) return { valid: false, error: 'Unknown KPI type' }

  // For PPM, lower is better
  if (kpiType === 'quality_ppm') {
    return {
      meetsTarget: value <= target,
      value,
      target,
      variance: target - value
    }
  }

  // For percentages, higher is better
  return {
    meetsTarget: value >= target,
    value,
    target,
    variance: value - target
  }
}

describe('Client Config Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  describe('System Defaults', () => {
    it('defines all required default values', () => {
      expect(SYSTEM_DEFAULTS.otd_mode).toBe('STANDARD')
      expect(SYSTEM_DEFAULTS.default_cycle_time_hours).toBe(0.05)
      expect(SYSTEM_DEFAULTS.quality_target_ppm).toBe(1000)
      expect(SYSTEM_DEFAULTS.efficiency_target_percent).toBe(85)
      expect(SYSTEM_DEFAULTS.fpy_target_percent).toBe(95)
      expect(SYSTEM_DEFAULTS.availability_target_percent).toBe(90)
    })

    it('uses valid OTD mode as default', () => {
      expect(validateOtdMode(SYSTEM_DEFAULTS.otd_mode)).toBe(true)
    })
  })

  describe('Client Config Overrides', () => {
    it('allows client to override OTD mode to TRUE', () => {
      const config = getEffectiveConfig('client_1')

      expect(config.otd_mode).toBe('TRUE')
    })

    it('allows client to override OTD mode to BOTH', () => {
      const config = getEffectiveConfig('client_2')

      expect(config.otd_mode).toBe('BOTH')
    })

    it('allows client to set custom cycle time', () => {
      const config = getEffectiveConfig('client_1')

      expect(config.default_cycle_time_hours).toBe(0.08)
    })

    it('allows client to set stricter quality target', () => {
      const config = getEffectiveConfig('client_1')

      expect(config.quality_target_ppm).toBe(500)
    })

    it('allows client to set higher efficiency target', () => {
      const config = getEffectiveConfig('client_1')

      expect(config.efficiency_target_percent).toBe(90)
    })
  })

  describe('Config Inheritance', () => {
    it('inherits unset values from system defaults', () => {
      const config = getEffectiveConfig('client_1')

      // Client 1 doesn't set these, should inherit
      expect(config.fpy_target_percent).toBe(95)
      expect(config.availability_target_percent).toBe(90)
    })

    it('fully inherits defaults for empty client config', () => {
      const config = getEffectiveConfig('client_3')

      expect(config.otd_mode).toBe('STANDARD')
      expect(config.default_cycle_time_hours).toBe(0.05)
      expect(config.quality_target_ppm).toBe(1000)
      expect(config.efficiency_target_percent).toBe(85)
    })

    it('returns defaults for unknown client', () => {
      const config = getEffectiveConfig('unknown_client')

      expect(config.otd_mode).toBe('STANDARD')
      expect(config.default_cycle_time_hours).toBe(0.05)
      expect(config.client_id).toBe('unknown_client')
    })

    it('correctly identifies inherited settings', () => {
      // Client 1 has these overridden
      expect(isSettingInherited('client_1', 'otd_mode')).toBe(false)
      expect(isSettingInherited('client_1', 'efficiency_target_percent')).toBe(false)

      // Client 1 doesn't set these
      expect(isSettingInherited('client_1', 'fpy_target_percent')).toBe(true)
      expect(isSettingInherited('client_1', 'availability_target_percent')).toBe(true)
    })

    it('identifies all settings as inherited for empty config', () => {
      expect(isSettingInherited('client_3', 'otd_mode')).toBe(true)
      expect(isSettingInherited('client_3', 'efficiency_target_percent')).toBe(true)
      expect(isSettingInherited('client_3', 'quality_target_ppm')).toBe(true)
    })

    it('identifies all settings as inherited for unknown client', () => {
      expect(isSettingInherited('unknown', 'otd_mode')).toBe(true)
    })
  })

  describe('OTD Mode Validation', () => {
    it('accepts STANDARD mode', () => {
      expect(validateOtdMode('STANDARD')).toBe(true)
    })

    it('accepts TRUE mode', () => {
      expect(validateOtdMode('TRUE')).toBe(true)
    })

    it('accepts BOTH mode', () => {
      expect(validateOtdMode('BOTH')).toBe(true)
    })

    it('rejects invalid mode', () => {
      expect(validateOtdMode('INVALID')).toBe(false)
      expect(validateOtdMode('')).toBe(false)
      expect(validateOtdMode(null)).toBe(false)
    })
  })

  describe('KPI Calculations with Client Config', () => {
    it('uses client-specific cycle time for efficiency', () => {
      // Client 1 has cycle time of 0.08 hours per unit
      // 100 units * 0.08 = 8 standard hours
      // 8 / 8 actual = 100% efficiency (capped at 100)
      const efficiency = calculateEfficiency(100, 8, 'client_1')

      expect(efficiency).toBe('100.00')
    })

    it('uses default cycle time for unknown client', () => {
      // Default cycle time is 0.05 hours per unit
      // 100 units * 0.05 = 5 standard hours
      // 5 / 8 actual = 62.5% efficiency
      const efficiency = calculateEfficiency(100, 8, 'unknown')

      expect(efficiency).toBe('62.50')
    })

    it('different clients get different efficiency results', () => {
      // Same production data, different cycle times
      const effClient1 = calculateEfficiency(100, 8, 'client_1') // 0.08 cycle time
      const effUnknown = calculateEfficiency(100, 8, 'unknown')  // 0.05 cycle time

      expect(parseFloat(effClient1)).toBeGreaterThan(parseFloat(effUnknown))
    })
  })

  describe('KPI Target Checking', () => {
    it('checks efficiency against client target', () => {
      // Client 1 has 90% efficiency target
      const result = checkKpiTarget('efficiency', 92, 'client_1')

      expect(result.meetsTarget).toBe(true)
      expect(result.target).toBe(90)
      expect(result.variance).toBe(2)
    })

    it('fails when below client target', () => {
      // Client 1 has 90% efficiency target
      const result = checkKpiTarget('efficiency', 85, 'client_1')

      expect(result.meetsTarget).toBe(false)
      expect(result.variance).toBe(-5)
    })

    it('uses default target for client without override', () => {
      // Client 3 inherits default 85% efficiency target
      const result = checkKpiTarget('efficiency', 86, 'client_3')

      expect(result.meetsTarget).toBe(true)
      expect(result.target).toBe(85)
    })

    it('checks quality PPM (lower is better)', () => {
      // Client 1 has 500 PPM target
      const goodResult = checkKpiTarget('quality_ppm', 400, 'client_1')
      const badResult = checkKpiTarget('quality_ppm', 600, 'client_1')

      expect(goodResult.meetsTarget).toBe(true)
      expect(badResult.meetsTarget).toBe(false)
    })

    it('uses inherited FPY target', () => {
      // Client 1 inherits 95% FPY target
      const result = checkKpiTarget('fpy', 96, 'client_1')

      expect(result.meetsTarget).toBe(true)
      expect(result.target).toBe(95)
    })

    it('handles unknown KPI type', () => {
      const result = checkKpiTarget('unknown_kpi', 50, 'client_1')

      expect(result.valid).toBe(false)
      expect(result.error).toBe('Unknown KPI type')
    })
  })

  describe('Multiple Client Comparison', () => {
    it('each client has unique effective config', () => {
      const config1 = getEffectiveConfig('client_1')
      const config2 = getEffectiveConfig('client_2')
      const config3 = getEffectiveConfig('client_3')

      expect(config1.otd_mode).toBe('TRUE')
      expect(config2.otd_mode).toBe('BOTH')
      expect(config3.otd_mode).toBe('STANDARD')
    })

    it('tracks correct client_id in each config', () => {
      const config1 = getEffectiveConfig('client_1')
      const config2 = getEffectiveConfig('client_2')

      expect(config1.client_id).toBe('client_1')
      expect(config2.client_id).toBe('client_2')
    })

    it('partial overrides merge correctly', () => {
      // Client 2 only overrides otd_mode and quality_target_ppm
      const config = getEffectiveConfig('client_2')

      expect(config.otd_mode).toBe('BOTH') // Override
      expect(config.quality_target_ppm).toBe(750) // Override
      expect(config.efficiency_target_percent).toBe(85) // Default
      expect(config.default_cycle_time_hours).toBe(0.05) // Default
    })
  })

  describe('Edge Cases', () => {
    it('handles null client_id', () => {
      const config = getEffectiveConfig(null)

      expect(config.otd_mode).toBe('STANDARD')
      expect(config.client_id).toBe(null)
    })

    it('handles undefined client_id', () => {
      const config = getEffectiveConfig(undefined)

      expect(config.otd_mode).toBe('STANDARD')
    })

    it('config does not mutate on retrieval', () => {
      const config1 = getEffectiveConfig('client_1')
      const config2 = getEffectiveConfig('client_1')

      // Should be equal but not the same object
      expect(config1).toEqual(config2)
      expect(config1).not.toBe(config2)
    })

    it('zero values are valid overrides', () => {
      // If a client config has a zero value, it should be used
      // Not fall back to default
      const testConfig = new Map([
        ['test_client', { efficiency_target_percent: 0 }]
      ])

      const clientConfig = testConfig.get('test_client') || {}
      const effective = { ...SYSTEM_DEFAULTS, ...clientConfig }

      expect(effective.efficiency_target_percent).toBe(0)
    })
  })
})
