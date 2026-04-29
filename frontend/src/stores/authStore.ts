import { defineStore } from 'pinia'
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

interface ActionResult<T = void> {
  success: boolean
  error?: string
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
          error: extractErrorDetail(error, 'Login failed'),
        }
      }
    },

    async register(userData: RegisterPayload): Promise<ActionResult> {
      try {
        const response = await api.register(userData)
        return { success: true, user: response.data as AuthUser }
      } catch (error) {
        return {
          success: false,
          error: extractErrorDetail(error, 'Registration failed'),
        }
      }
    },

    async forgotPassword(email: string): Promise<ActionResult> {
      this.passwordResetSent = false
      this.passwordResetError = null

      try {
        await api.forgotPassword(email)
        this.passwordResetSent = true
        return { success: true, message: 'Password reset email sent' }
      } catch (error) {
        this.passwordResetError = extractErrorDetail(error, 'Failed to send reset email')
        return {
          success: false,
          error: this.passwordResetError,
        }
      }
    },

    async resetPassword(token: string, newPassword: string): Promise<ActionResult> {
      try {
        await api.resetPassword(token, newPassword)
        return { success: true, message: 'Password reset successfully' }
      } catch (error) {
        return {
          success: false,
          error: extractErrorDetail(error, 'Failed to reset password'),
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
          error: extractErrorDetail(error, 'Invalid or expired token'),
        }
      }
    },

    async changePassword(currentPassword: string, newPassword: string): Promise<ActionResult> {
      try {
        await api.changePassword(currentPassword, newPassword)
        return { success: true, message: 'Password changed successfully' }
      } catch (error) {
        return {
          success: false,
          error: extractErrorDetail(error, 'Failed to change password'),
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
