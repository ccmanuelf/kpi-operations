/**
 * Every call site of a delete action must inspect the result it returns.
 *
 * productionDataStore's actions catch their own errors and resolve with
 * `{success: false}` rather than throwing, so `await`-ing one inside a
 * try/catch does NOT route a failure to the catch. Three call sites made that
 * mistake at once and shipped: on a refused delete they removed the row from
 * the grid and showed a green "deleted successfully".
 *
 * A convention that has already been broken by everyone who touched it is not a
 * convention, so this is a gate rather than a comment. It reads the source
 * because the failure is a MISSING statement — nothing runtime can observe a
 * call site that forgot to look at its own return value.
 *
 * Mutation proof: drop `const result =` from any of the three delete call sites
 * and this fails, naming the file and line.
 */
import { describe, it, expect } from 'vitest'
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { dirname, join, resolve, relative } from 'node:path'
import { fileURLToPath } from 'node:url'

const SRC = resolve(dirname(fileURLToPath(import.meta.url)), '../../')
const STORE = join(SRC, 'stores', 'productionDataStore.ts')

function walk(dir: string): string[] {
  const out: string[] = []
  for (const name of readdirSync(dir)) {
    const p = join(dir, name)
    if (statSync(p).isDirectory()) {
      if (/node_modules|__tests__/.test(p)) continue
      out.push(...walk(p))
    } else if (/\.(ts|vue)$/.test(p) && !/\.spec\.ts$/.test(p) && !/\.d\.ts$/.test(p)) {
      out.push(p)
    }
  }
  return out
}

/** Actions declared on the store, read from the source rather than listed.
 *
 * Covers fetch as well as delete: both resolve {success:false} instead of
 * throwing, and both had every call site ignoring it. A failed delete announced
 * a success; a failed fetch left the grid rendering "no rows", which a user
 * cannot tell apart from an empty dataset. */
const guardedActions = [
  ...readFileSync(STORE, 'utf8').matchAll(
    /async ((?:delete|fetch)\w+)\([^)]*\):\s*Promise<ActionResult/g,
  ),
].map((m) => m[1])

describe('actions that resolve {success:false} are always inspected', () => {
  it('finds the store\'s guarded actions', () => {
    // If this drops to zero the gate below passes vacuously.
    expect(guardedActions.length).toBeGreaterThanOrEqual(8)
  })

  it('every call site captures the result', () => {
    const ignored: string[] = []
    for (const file of walk(SRC)) {
      if (file === STORE) continue // its own api.* calls throw and are wrapped
      const src = readFileSync(file, 'utf8')
      for (const action of guardedActions) {
        for (const m of src.matchAll(new RegExp(String.raw`await\s+\w+\.${action}\(`, 'g'))) {
          const before = src.slice(Math.max(0, m.index! - 60), m.index!)
          if (!/(?:const|let)\s+\w+\s*=\s*$/.test(before)) {
            const line = src.slice(0, m.index!).split('\n').length
            ignored.push(`${relative(SRC, file)}:${line} discards the result of ${action}`)
          }
        }
      }
    }
    expect(ignored).toEqual([])
  })
})
