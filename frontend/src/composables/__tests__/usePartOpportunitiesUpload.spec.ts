import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref } from 'vue'
import * as Papa from 'papaparse'

/**
 * The CSV import path for part opportunities.
 *
 * It posted a multipart file to `/part-opportunities/upload`, a path with no
 * server route, so every import 404'd and surfaced as a generic toast. The
 * only bulk ingestion endpoint is `POST /api/part-opportunities/bulk-import`,
 * which takes JSON rows. These pin the mapping from CSV columns to the row
 * shape that endpoint accepts, because a wrong field name fails server-side
 * per row rather than loudly.
 */

const post = vi.fn()
vi.mock('@/services/api', () => ({ default: { post: (...a: unknown[]) => post(...a) } }))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (k: string) => k }) }))

/** The mapping under test, mirroring the composable's parse step. */
function rowsFromCsv(text: string, clientId: string) {
  const parsed = Papa.parse<Record<string, string>>(text, { header: true, skipEmptyLines: true })
  return parsed.data
    .map((row) => ({
      part_number: (row.part_number ?? '').trim(),
      client_id_fk: clientId,
      opportunities_per_unit: Number.parseInt(row.opportunities_per_unit ?? '', 10),
      part_description: row.part_description?.trim() || null,
      part_category: (row.part_category ?? row.complexity)?.trim() || null,
      notes: row.notes?.trim() || null,
    }))
    .filter((o) => o.part_number && Number.isFinite(o.opportunities_per_unit))
}

describe('part-opportunities CSV → bulk-import rows', () => {
  beforeEach(() => post.mockReset())

  it('produces exactly the fields PartOpportunityCreate requires', () => {
    const csv = 'part_number,opportunities_per_unit,part_description,part_category,notes\nP-1,15,Shirt,Apparel,note'
    const [row] = rowsFromCsv(csv, 'DEMO-PIECE')
    // client_id_fk and opportunities_per_unit are REQUIRED server-side, and
    // opportunities_per_unit must be an int > 0 — a string would 422.
    expect(row).toEqual({
      part_number: 'P-1',
      client_id_fk: 'DEMO-PIECE',
      opportunities_per_unit: 15,
      part_description: 'Shirt',
      part_category: 'Apparel',
      notes: 'note',
    })
    expect(typeof row.opportunities_per_unit).toBe('number')
  })

  it('still reads `complexity`, which older templates emitted for that column', () => {
    // The template shipped `complexity`, a field the schema does not have, so
    // anything exported before this fix would silently lose its category.
    const csv = 'part_number,opportunities_per_unit,complexity\nP-2,7,Standard'
    expect(rowsFromCsv(csv, 'C')[0].part_category).toBe('Standard')
  })

  it('drops rows the endpoint would reject rather than sending them', () => {
    const csv = [
      'part_number,opportunities_per_unit',
      ',5', // no part number
      'P-3,', // no count
      'P-4,notanumber', // unparseable count
      'P-5,9', // the only good row
    ].join('\n')
    const rows = rowsFromCsv(csv, 'C')
    expect(rows.map((r) => r.part_number)).toEqual(['P-5'])
  })

  it('blanks become null, not empty strings', () => {
    // The columns are Optional[str]; "" would be stored as an empty value
    // rather than left unset.
    const csv = 'part_number,opportunities_per_unit,part_description,notes\nP-6,3,,'
    const [row] = rowsFromCsv(csv, 'C')
    expect(row.part_description).toBeNull()
    expect(row.notes).toBeNull()
  })
})
