import { describe, it, expect } from 'vitest'
import en from '../locales/en.json'
import es from '../locales/es.json'

function flatKeys(obj: Record<string, unknown>, prefix = ''): string[] {
  const out: string[] = []
  for (const [k, v] of Object.entries(obj)) {
    const key = prefix ? `${prefix}.${k}` : k
    if (v && typeof v === 'object' && !Array.isArray(v)) {
      out.push(...flatKeys(v as Record<string, unknown>, key))
    } else {
      out.push(key)
    }
  }
  return out
}

describe('locale parity (en <-> es)', () => {
  it('en and es define exactly the same key set', () => {
    const enKeys = flatKeys(en as Record<string, unknown>).sort()
    const esKeys = flatKeys(es as Record<string, unknown>).sort()
    const missingInEs = enKeys.filter((k) => !esKeys.includes(k))
    const missingInEn = esKeys.filter((k) => !enKeys.includes(k))
    expect({ missingInEs, missingInEn }).toEqual({ missingInEs: [], missingInEn: [] })
  })
})
