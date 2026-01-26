/**
 * Unit tests for Auth Store
 * Tests authentication state management: login, register, logout, forgot password, reset password
 * Phase 8: Comprehensive auth coverage
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '../authStore'

// Mock the API module
vi.mock('@/services/api', () => ({
  default: {
    login: vi.fn(),
    register: vi.fn(),
    forgotPassword: vi.fn(),
    resetPassword: vi.fn(),
    verifyResetToken: vi.fn(),
    changePassword: vi.fn()
  }
}))

import api from '@/services/api'

describe('Auth Store', () => {
  let localStorageMock

  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()

    // Mock localStorage
    localStorageMock = {
      getItem: vi.fn(),
      setItem: vi.fn(),
      removeItem: vi.fn()
    }
    Object.defineProperty(global, 'localStorage', {
      value: localStorageMock,
      writable: true
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('State Initialization', () => {
    it('initializes with null user when localStorage is empty', () => {
      localStorageMock.getItem.mockReturnValue(null)
      const store = useAuthStore()

      expect(store.user).toBeNull()
      expect(store.token).toBeNull()
    })

    it('initializes with stored user from localStorage', () => {
      const storedUser = { user_id: 1, email: 'test@test.com', role: 'admin' }
      localStorageMock.getItem.mockImplementation((key) => {
        if (key === 'user') return JSON.stringify(storedUser)
        if (key === 'access_token') return 'stored-token'
        return null
      })

      // Re-create pinia to trigger fresh initialization
      setActivePinia(createPinia())
      const store = useAuthStore()

      expect(store.token).toBe('stored-token')
    })

    it('initializes password reset state as false', () => {
      const store = useAuthStore()

      expect(store.passwordResetSent).toBe(false)
      expect(store.passwordResetError).toBeNull()
    })
  })

  describe('Getters', () => {
    it('isAuthenticated returns true when token exists', () => {
      const store = useAuthStore()
      store.token = 'valid-token'

      expect(store.isAuthenticated).toBe(true)
    })

    it('isAuthenticated returns false when token is null', () => {
      const store = useAuthStore()
      store.token = null

      expect(store.isAuthenticated).toBe(false)
    })

    it('isAdmin returns true for admin users', () => {
      const store = useAuthStore()
      store.user = { role: 'admin' }

      expect(store.isAdmin).toBe(true)
    })

    it('isAdmin returns false for non-admin users', () => {
      const store = useAuthStore()
      store.user = { role: 'operator' }

      expect(store.isAdmin).toBe(false)
    })

    it('isSupervisor returns true for admin users', () => {
      const store = useAuthStore()
      store.user = { role: 'admin' }

      expect(store.isSupervisor).toBe(true)
    })

    it('isSupervisor returns true for supervisor users', () => {
      const store = useAuthStore()
      store.user = { role: 'supervisor' }

      expect(store.isSupervisor).toBe(true)
    })

    it('isSupervisor returns false for operator users', () => {
      const store = useAuthStore()
      store.user = { role: 'operator' }

      expect(store.isSupervisor).toBe(false)
    })

    it('currentUser returns the user object', () => {
      const store = useAuthStore()
      const testUser = { user_id: 1, email: 'test@test.com' }
      store.user = testUser

      expect(store.currentUser).toEqual(testUser)
    })
  })

  describe('Login Action', () => {
    it('logs in successfully and stores token', async () => {
      const mockResponse = {
        data: {
          access_token: 'new-token',
          user: { user_id: 1, email: 'test@test.com', role: 'admin' }
        }
      }
      api.login.mockResolvedValue(mockResponse)

      const store = useAuthStore()
      const result = await store.login({ email: 'test@test.com', password: 'password' })

      expect(result.success).toBe(true)
      expect(store.token).toBe('new-token')
      expect(store.user).toEqual(mockResponse.data.user)
      expect(localStorageMock.setItem).toHaveBeenCalledWith('access_token', 'new-token')
      expect(localStorageMock.setItem).toHaveBeenCalledWith('user', JSON.stringify(mockResponse.data.user))
    })

    it('handles login failure with server error message', async () => {
      api.login.mockRejectedValue({
        response: { data: { detail: 'Invalid credentials' } }
      })

      const store = useAuthStore()
      const result = await store.login({ email: 'test@test.com', password: 'wrong' })

      expect(result.success).toBe(false)
      expect(result.error).toBe('Invalid credentials')
      expect(store.token).toBeNull()
    })

    it('handles login failure with generic error', async () => {
      api.login.mockRejectedValue(new Error('Network error'))

      const store = useAuthStore()
      const result = await store.login({ email: 'test@test.com', password: 'password' })

      expect(result.success).toBe(false)
      expect(result.error).toBe('Login failed')
    })
  })

  describe('Register Action', () => {
    it('registers successfully', async () => {
      const mockUser = { user_id: 1, email: 'new@test.com' }
      api.register.mockResolvedValue({ data: mockUser })

      const store = useAuthStore()
      const result = await store.register({
        email: 'new@test.com',
        password: 'password',
        full_name: 'Test User'
      })

      expect(result.success).toBe(true)
      expect(result.user).toEqual(mockUser)
    })

    it('handles registration failure', async () => {
      api.register.mockRejectedValue({
        response: { data: { detail: 'Email already exists' } }
      })

      const store = useAuthStore()
      const result = await store.register({
        email: 'existing@test.com',
        password: 'password'
      })

      expect(result.success).toBe(false)
      expect(result.error).toBe('Email already exists')
    })

    it('handles registration failure with generic error', async () => {
      api.register.mockRejectedValue(new Error('Network error'))

      const store = useAuthStore()
      const result = await store.register({
        email: 'test@test.com',
        password: 'password'
      })

      expect(result.success).toBe(false)
      expect(result.error).toBe('Registration failed')
    })
  })

  describe('Forgot Password Action', () => {
    it('sends password reset email successfully', async () => {
      api.forgotPassword.mockResolvedValue({ data: { message: 'Email sent' } })

      const store = useAuthStore()
      const result = await store.forgotPassword('user@test.com')

      expect(result.success).toBe(true)
      expect(result.message).toBe('Password reset email sent')
      expect(store.passwordResetSent).toBe(true)
      expect(store.passwordResetError).toBeNull()
    })

    it('handles forgot password failure', async () => {
      api.forgotPassword.mockRejectedValue({
        response: { data: { detail: 'User not found' } }
      })

      const store = useAuthStore()
      const result = await store.forgotPassword('nonexistent@test.com')

      expect(result.success).toBe(false)
      expect(result.error).toBe('User not found')
      expect(store.passwordResetSent).toBe(false)
      expect(store.passwordResetError).toBe('User not found')
    })

    it('handles forgot password with generic error', async () => {
      api.forgotPassword.mockRejectedValue(new Error('Network error'))

      const store = useAuthStore()
      const result = await store.forgotPassword('user@test.com')

      expect(result.success).toBe(false)
      expect(result.error).toBe('Failed to send reset email')
    })

    it('clears previous error state before new request', async () => {
      const store = useAuthStore()
      store.passwordResetError = 'Previous error'
      store.passwordResetSent = true

      api.forgotPassword.mockResolvedValue({ data: {} })
      await store.forgotPassword('user@test.com')

      // Error should be cleared at start
      expect(store.passwordResetError).toBeNull()
    })
  })

  describe('Reset Password Action', () => {
    it('resets password successfully', async () => {
      api.resetPassword.mockResolvedValue({ data: { message: 'Success' } })

      const store = useAuthStore()
      const result = await store.resetPassword('valid-token', 'newPassword123')

      expect(result.success).toBe(true)
      expect(result.message).toBe('Password reset successfully')
    })

    it('handles reset password failure with expired token', async () => {
      api.resetPassword.mockRejectedValue({
        response: { data: { detail: 'Token expired' } }
      })

      const store = useAuthStore()
      const result = await store.resetPassword('expired-token', 'newPassword123')

      expect(result.success).toBe(false)
      expect(result.error).toBe('Token expired')
    })

    it('handles reset password failure with invalid token', async () => {
      api.resetPassword.mockRejectedValue({
        response: { data: { detail: 'Invalid token' } }
      })

      const store = useAuthStore()
      const result = await store.resetPassword('invalid-token', 'newPassword123')

      expect(result.success).toBe(false)
      expect(result.error).toBe('Invalid token')
    })

    it('handles reset password with generic error', async () => {
      api.resetPassword.mockRejectedValue(new Error('Network error'))

      const store = useAuthStore()
      const result = await store.resetPassword('token', 'newPassword123')

      expect(result.success).toBe(false)
      expect(result.error).toBe('Failed to reset password')
    })
  })

  describe('Verify Reset Token Action', () => {
    it('verifies valid token successfully', async () => {
      api.verifyResetToken.mockResolvedValue({
        data: { valid: true, email: 'user@test.com' }
      })

      const store = useAuthStore()
      const result = await store.verifyResetToken('valid-token')

      expect(result.success).toBe(true)
      expect(result.valid).toBe(true)
      expect(result.email).toBe('user@test.com')
    })

    it('handles invalid token verification', async () => {
      api.verifyResetToken.mockRejectedValue({
        response: { data: { detail: 'Token expired' } }
      })

      const store = useAuthStore()
      const result = await store.verifyResetToken('expired-token')

      expect(result.success).toBe(false)
      expect(result.valid).toBe(false)
      expect(result.error).toBe('Token expired')
    })

    it('handles verification with generic error', async () => {
      api.verifyResetToken.mockRejectedValue(new Error('Network error'))

      const store = useAuthStore()
      const result = await store.verifyResetToken('token')

      expect(result.success).toBe(false)
      expect(result.error).toBe('Invalid or expired token')
    })
  })

  describe('Change Password Action', () => {
    it('changes password successfully', async () => {
      api.changePassword.mockResolvedValue({ data: { message: 'Changed' } })

      const store = useAuthStore()
      const result = await store.changePassword('oldPassword', 'newPassword')

      expect(result.success).toBe(true)
      expect(result.message).toBe('Password changed successfully')
    })

    it('handles incorrect current password', async () => {
      api.changePassword.mockRejectedValue({
        response: { data: { detail: 'Current password is incorrect' } }
      })

      const store = useAuthStore()
      const result = await store.changePassword('wrongOld', 'newPassword')

      expect(result.success).toBe(false)
      expect(result.error).toBe('Current password is incorrect')
    })

    it('handles change password with generic error', async () => {
      api.changePassword.mockRejectedValue(new Error('Network error'))

      const store = useAuthStore()
      const result = await store.changePassword('old', 'new')

      expect(result.success).toBe(false)
      expect(result.error).toBe('Failed to change password')
    })
  })

  describe('Logout Action', () => {
    it('clears token and user on logout', () => {
      const store = useAuthStore()
      store.token = 'some-token'
      store.user = { user_id: 1 }

      store.logout()

      expect(store.token).toBeNull()
      expect(store.user).toBeNull()
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('access_token')
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('user')
    })

    it('clears password reset state on logout', () => {
      const store = useAuthStore()
      store.passwordResetSent = true
      store.passwordResetError = 'Some error'

      store.logout()

      expect(store.passwordResetSent).toBe(false)
      expect(store.passwordResetError).toBeNull()
    })
  })

  describe('Clear Password Reset State', () => {
    it('clears password reset sent flag', () => {
      const store = useAuthStore()
      store.passwordResetSent = true
      store.passwordResetError = 'Error'

      store.clearPasswordResetState()

      expect(store.passwordResetSent).toBe(false)
      expect(store.passwordResetError).toBeNull()
    })
  })
})
