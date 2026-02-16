import { defineStore } from 'pinia'
import api from '@/services/api'

// SECURITY NOTE: JWT tokens are stored in localStorage for simplicity in the
// demo/development phase. This is vulnerable to XSS but acceptable because:
// 1. Vue's template escaping mitigates XSS in rendered content
// 2. CSP headers block inline scripts
// 3. Tokens have 30-minute expiry
// For production hardening, consider httpOnly cookies with CSRF protection.
// See docs/SECURITY.md for the full risk acceptance analysis.
export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: JSON.parse(localStorage.getItem('user') || 'null'),
    token: localStorage.getItem('access_token') || null,
    passwordResetSent: false,
    passwordResetError: null
  }),

  getters: {
    isAuthenticated: (state) => !!state.token,
    currentUser: (state) => state.user,
    isAdmin: (state) => state.user?.role === 'admin',
    isSupervisor: (state) => ['admin', 'supervisor'].includes(state.user?.role)
  },

  actions: {
    async login(credentials) {
      try {
        const response = await api.login(credentials)
        const { access_token, user } = response.data

        this.token = access_token
        this.user = user

        localStorage.setItem('access_token', access_token)
        localStorage.setItem('user', JSON.stringify(user))

        return { success: true }
      } catch (error) {
        return {
          success: false,
          error: error.response?.data?.detail || 'Login failed'
        }
      }
    },

    async register(userData) {
      try {
        const response = await api.register(userData)
        return { success: true, user: response.data }
      } catch (error) {
        return {
          success: false,
          error: error.response?.data?.detail || 'Registration failed'
        }
      }
    },

    async forgotPassword(email) {
      this.passwordResetSent = false
      this.passwordResetError = null

      try {
        await api.forgotPassword(email)
        this.passwordResetSent = true
        return { success: true, message: 'Password reset email sent' }
      } catch (error) {
        this.passwordResetError = error.response?.data?.detail || 'Failed to send reset email'
        return {
          success: false,
          error: this.passwordResetError
        }
      }
    },

    async resetPassword(token, newPassword) {
      try {
        await api.resetPassword(token, newPassword)
        return { success: true, message: 'Password reset successfully' }
      } catch (error) {
        return {
          success: false,
          error: error.response?.data?.detail || 'Failed to reset password'
        }
      }
    },

    async verifyResetToken(token) {
      try {
        const response = await api.verifyResetToken(token)
        return { success: true, valid: true, email: response.data?.email }
      } catch (error) {
        return {
          success: false,
          valid: false,
          error: error.response?.data?.detail || 'Invalid or expired token'
        }
      }
    },

    async changePassword(currentPassword, newPassword) {
      try {
        await api.changePassword(currentPassword, newPassword)
        return { success: true, message: 'Password changed successfully' }
      } catch (error) {
        return {
          success: false,
          error: error.response?.data?.detail || 'Failed to change password'
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
    }
  }
})
