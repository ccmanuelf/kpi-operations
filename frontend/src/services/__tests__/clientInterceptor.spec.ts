/**
 * Tests the REAL response interceptor registered on the single axios instance,
 * reached through `api.interceptors.response.handlers[0].rejected`.
 *
 * Deliberately a separate file from `client.spec.ts`, which re-implements the
 * interceptor inside its own test bodies and therefore cannot catch a change
 * to the shipped one.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { api } from '@/services/api/client'

interface RejectedHandler {
  (_error: unknown): Promise<never>
}

const rejectedHandler = (
  api.interceptors.response as unknown as { handlers: Array<{ rejected: RejectedHandler }> }
).handlers[0].rejected

/** Runs the interceptor and returns the error it re-rejects with. */
const runInterceptor = async (error: unknown): Promise<unknown> => {
  try {
    await rejectedHandler(error)
  } catch (rejected) {
    return rejected
  }
  throw new Error('interceptor resolved; it must always re-reject')
}

const axiosLikeError = (status: number, detail: unknown) => ({
  response: { status, data: { detail } },
})

describe('response interceptor — structured detail', () => {
  it('flattens a 409 blocked_by payload into the localized sentence', async () => {
    const error = axiosLikeError(409, {
      message: 'Cannot delete this WORK_ORDER record while other records still reference it.',
      blocked_by: [
        { table: 'JOB', count: 1 },
        { table: 'PRODUCTION_ENTRY', count: 4 },
      ],
    })

    await runInterceptor(error)

    expect(error.response.data.detail).toBe(
      'Cannot delete this record — other records still reference it: ' +
        'Job (1), Production entries (4). Delete or reassign them first.',
    )
  })

  it('keeps the structured payload on the error for surfaces that can render rows', async () => {
    const detail = { message: 'blocked', blocked_by: [{ table: 'JOB', count: 1 }] }
    const error = axiosLikeError(409, detail)

    const rejected = (await runInterceptor(error)) as { structuredDetail?: unknown }

    expect(rejected.structuredDetail).toEqual(detail)
  })

  it('flattens a 422 hidden_parents payload', async () => {
    const error = axiosLikeError(422, {
      message: 'Cannot reference a deleted record: WORK_ORDER WO-0002.',
      hidden_parents: [{ table: 'WORK_ORDER', id: 'WO-0002' }],
    })

    await runInterceptor(error)

    expect(error.response.data.detail).toBe(
      'Cannot reference a deleted record: Work order WO-0002. ' +
        'It has been deleted and is no longer available.',
    )
  })

  it('formats a FastAPI validation array instead of leaving [object Object]', async () => {
    // detail is an ARRAY here and 422 is the same status our hidden-parent guard
    // uses. It must be recognised as FastAPI's own shape, not ours.
    const error = axiosLikeError(422, [
      { type: 'missing', loc: ['body', 'work_order_id'], msg: 'Field required', input: {} },
    ])

    await runInterceptor(error)

    expect(error.response.data.detail).toBe('Work order: This field is required')
  })

  it('never mistakes a validation array for a structured delete payload', async () => {
    // The guarantee the byte-identical version of this test was really
    // protecting: our blocked_by/hidden_parents handling must not touch it, so
    // no structuredDetail is attached and no delete wording appears.
    const error = axiosLikeError(422, [
      { type: 'missing', loc: ['body', 'work_order_id'], msg: 'Field required', input: {} },
    ])

    await runInterceptor(error)

    expect((error as { structuredDetail?: unknown }).structuredDetail).toBeUndefined()
    expect(error.response.data.detail).not.toContain('reference')
    expect(error.response.data.detail).not.toContain('deleted')
  })

  it('leaves an array that is not a validation payload alone', async () => {
    const error = axiosLikeError(422, [{ nope: 1 }])
    const before = structuredClone(error.response.data.detail)

    await runInterceptor(error)

    expect(error.response.data.detail).toEqual(before)
  })

  it('leaves a string detail alone', async () => {
    const error = axiosLikeError(404, 'Work order not found')

    await runInterceptor(error)

    expect(error.response.data.detail).toBe('Work order not found')
  })

  it('survives a network error with no response', async () => {
    const error = { message: 'Network Error' }

    expect(await runInterceptor(error)).toBe(error)
  })
})

describe('response interceptor — 401 branch', () => {
  let removed: string[]
  let originalLocalStorage: PropertyDescriptor | undefined

  beforeEach(() => {
    removed = []
    originalLocalStorage = Object.getOwnPropertyDescriptor(globalThis, 'localStorage')
    // The interceptor reads the bare `localStorage` global, not
    // `window.localStorage` — spying on Storage.prototype misses it.
    Object.defineProperty(globalThis, 'localStorage', {
      value: { removeItem: (key: string) => removed.push(key) },
      writable: true,
      configurable: true,
    })
    Object.defineProperty(window, 'location', {
      value: { href: '' },
      writable: true,
      configurable: true,
    })
  })

  afterEach(() => {
    if (originalLocalStorage) {
      Object.defineProperty(globalThis, 'localStorage', originalLocalStorage)
    }
    vi.restoreAllMocks()
  })

  it('clears the session and redirects to /login', async () => {
    await runInterceptor(axiosLikeError(401, 'Not authenticated'))

    expect(removed).toEqual(['access_token', 'user'])
    expect(window.location.href).toBe('/login')
  })
})
