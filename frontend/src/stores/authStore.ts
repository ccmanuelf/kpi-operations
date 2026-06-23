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
  // No HTTP response (network error / CORS), an aborted/timed-out request, or a
  // gateway error are all signs the backend is still spinning up on free hosting.
  if (
    status === undefined ||
    status === 0 ||
    status === 502 ||
    status === 503 ||
    status === 504 ||
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
    async login(credentials: LoginCredentials): Promise<ActionResult> {
      try {
        const response = await api.login(credentials)
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

    // Best-effort backend warm-up: ping the health endpoint as the login page
    // mounts so a sleeping free-tier API starts booting while the user types.
    // Uses a bare fetch (NOT the api client) on purpose — going through the
    // shared axios client would run the 401 interceptor, which redirects to
    // /login on any 401 and would loop the login page. `no-cors` is fine: we
    // only need the request to reach (and wake) the backend, not read it.
    async warmUpBackend(): Promise<void> {
      const base = (import.meta.env.VITE_API_URL as string | undefined) || '/api/v1'
      const root = base.replace(/\/api(\/v1)?\/?$/, '')
      try {
        await fetch(`${root}/health/live`, { method: 'GET', mode: 'no-cors' })
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
