import { defineStore } from 'pinia'
import i18n from '@/i18n'
import api from '@/services/api'
import type { LoginCredentials, RegisterPayload } from '@/services/api/auth'

// SECURITY NOTE: JWT tokens are stored in localStorage for simplicity in the
// demo/development phase. This is vulnerable to XSS but acceptable because:
// 1. Vue's template escaping mitigates XSS in rendered content
// 2. CSP headers block inline scripts
// 3. Tokens have 30-minute expiry
// For production hardening, consider httpOnly cookies with CSRF protection.
// See docs/SECURITY.md for the full risk acceptance analysis.

export interface AuthUser {
  user_id?: string | number
  username?: string
  email?: string
  role?: string
  client_id_assigned?: string | null
  full_name?: string
  [key: string]: unknown
}

interface AuthState {
  user: AuthUser | null
  token: string | null
  passwordResetSent: boolean
  passwordResetError: string | null
}

// Classifies a failed auth call so the UI can distinguish a backend that is
// still cold-starting (free hosting) from genuinely wrong credentials.
//   'waking'  — no response / 502-504 / network/timeout → server warming up
//   'invalid' — 401 → wrong username or password
//   'error'   — any other failure
type AuthFailureCode = 'waking' | 'invalid' | 'error'

interface ActionResult<T = void> {
  success: boolean
  error?: string
  code?: AuthFailureCode
  message?: string
  user?: AuthUser
  valid?: boolean
  email?: string
  data?: T
}

const readStoredUser = (): AuthUser | null => {
  try {
    return JSON.parse(localStorage.getItem('user') || 'null') as AuthUser | null
  } catch {
    return null
  }
}

const extractErrorDetail = (error: unknown, fallback: string): string => {
  const ax = error as { response?: { data?: { detail?: string } } }
  return ax?.response?.data?.detail || fallback
}

const classifyAuthFailure = (error: unknown): AuthFailureCode => {
  const ax = error as { response?: { status?: number }; code?: string }
  const status = ax?.response?.status
  if (status === 401) return 'invalid'
  // While a free-tier service is hibernating, Render's edge throttles wake-up
  // requests and answers HTTP 429 (text/plain "Too Many Requests") until the
  // container is up — verified live, the response carries
  // `x-render-routing: hibernate-rate-limited`. A cold start takes ~90s, during
  // which every login attempt is a 429. The app itself never returns 429, so a 429
  // here always means "the backend is asleep, hold on", not a bad password.
  // No HTTP response (network error / CORS), an aborted/timed-out request, or ANY
  // server-side 5xx are the other cold-start signatures: the proxy returns
  // 502/503/504 before the app accepts connections, and the app can return a
  // transient 500 in the window where it is up but still (re-)seeding the demo DB.
  // None of these mean the user typed a bad password, so we surface "waking up" and
  // auto-retry instead of the scary "login failed".
  if (
    status === undefined ||
    status === 0 ||
    status === 429 ||
    (status >= 500 && status <= 599) ||
    ax?.code === 'ECONNABORTED' ||
    ax?.code === 'ERR_NETWORK'
  ) {
    return 'waking'
  }
  return 'error'
}

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    user: readStoredUser(),
    token: localStorage.getItem('access_token') || null,
    passwordResetSent: false,
    passwordResetError: null,
  }),

  getters: {
    isAuthenticated: (state): boolean => !!state.token,
    currentUser: (state): AuthUser | null => state.user,
    isAdmin: (state): boolean => state.user?.role === 'admin',
    isSupervisor: (state): boolean =>
      ['admin', 'supervisor'].includes(state.user?.role ?? ''),
  },

  actions: {
    async login(credentials: LoginCredentials, timeoutMs?: number): Promise<ActionResult> {
      try {
        const response = await api.login(credentials, timeoutMs)
        const { access_token, user } = response.data as {
          access_token: string
          user: AuthUser
        }

        this.token = access_token
        this.user = user

        localStorage.setItem('access_token', access_token)
        localStorage.setItem('user', JSON.stringify(user))

        return { success: true }
      } catch (error) {
        return {
          success: false,
          code: classifyAuthFailure(error),
          error: extractErrorDetail(error, i18n.global.t('auth.loginFailed')),
        }
      }
    },

    // Best-effort backend warm-up: ping the backend health endpoint as the login
    // page mounts so a sleeping free-tier API starts booting while the user reads
    // and types (a cold start is ~90s, so the head start matters).
    //
    // Must hit a path UNDER the API base (e.g. /api/v1/health/live): nginx answers
    // the SPA-relative /health locally and never forwards it, so pinging /health/live
    // would only wake the frontend, not the backend. /api/* is proxied to the backend
    // (and /api/v1/health/live + /api/health/live are real backend routes), so this
    // reaches Render's edge and triggers the wake.
    //
    // Bare fetch (NOT the api client) on purpose — the shared axios client runs a 401
    // interceptor that redirects to /login and would loop the page. `no-cors` is fine:
    // we only need the request to reach (and wake) the backend, not read the response.
    async warmUpBackend(): Promise<void> {
      const base = (import.meta.env.VITE_API_URL as string | undefined) || '/api/v1'
      try {
        await fetch(`${base}/health/live`, { method: 'GET', mode: 'no-cors' })
      } catch {
        /* best-effort — a sleeping or unreachable backend just stays unwarmed */
      }
    },

    async register(userData: RegisterPayload): Promise<ActionResult> {
      try {
        const response = await api.register(userData)
        return { success: true, user: response.data as AuthUser }
      } catch (error) {
        return {
          success: false,
          error: extractErrorDetail(error, i18n.global.t('auth.registrationFailed')),
        }
      }
    },

    async forgotPassword(email: string): Promise<ActionResult> {
      this.passwordResetSent = false
      this.passwordResetError = null

      try {
        await api.forgotPassword(email)
        this.passwordResetSent = true
        return { success: true, message: i18n.global.t('auth.passwordResetSuccess') }
      } catch (error) {
        this.passwordResetError = extractErrorDetail(error, i18n.global.t('auth.forgotPasswordFailed'))
        return {
          success: false,
          error: this.passwordResetError,
        }
      }
    },

    async resetPassword(token: string, newPassword: string): Promise<ActionResult> {
      try {
        await api.resetPassword(token, newPassword)
        return { success: true, message: i18n.global.t('auth.resetPasswordSuccess') }
      } catch (error) {
        return {
          success: false,
          error: extractErrorDetail(error, i18n.global.t('auth.resetPasswordFailed')),
        }
      }
    },

    async verifyResetToken(token: string): Promise<ActionResult> {
      try {
        const response = await api.verifyResetToken(token)
        const data = response.data as { email?: string } | undefined
        return { success: true, valid: true, email: data?.email }
      } catch (error) {
        return {
          success: false,
          valid: false,
          error: extractErrorDetail(error, i18n.global.t('auth.verifyTokenFailed')),
        }
      }
    },

    async changePassword(currentPassword: string, newPassword: string): Promise<ActionResult> {
      try {
        await api.changePassword(currentPassword, newPassword)
        return { success: true, message: i18n.global.t('auth.changePasswordSuccess') }
      } catch (error) {
        return {
          success: false,
          error: extractErrorDetail(error, i18n.global.t('auth.changePasswordFailed')),
        }
      }
    },

    logout() {
      this.token = null
      this.user = null
      this.passwordResetSent = false
      this.passwordResetError = null
      localStorage.removeItem('access_token')
      localStorage.removeItem('user')
    },

    clearPasswordResetState() {
      this.passwordResetSent = false
      this.passwordResetError = null
    },
  },
})
