/**
 * Unit tests for Auth API module
 * Tests authentication API calls: login, register, forgot password, reset password
 * Phase 8: Comprehensive auth coverage
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock the client module - must use inline functions for hoisting
vi.mock('../api/client', () => ({
  default: {
    post: vi.fn(),
    get: vi.fn()
  }
}))

import api from '../api/client'
import * as authApi from '../api/auth'

describe('Auth API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('login', () => {
    it('calls POST /auth/login with credentials', async () => {
      const credentials = { email: 'test@test.com', password: 'password123' }
      const mockResponse = {
        data: { access_token: 'token', user: { id: 1 } }
      }
      api.post.mockResolvedValue(mockResponse)

      const result = await authApi.login(credentials)

      expect(api.post).toHaveBeenCalledWith('/auth/login', credentials)
      expect(result).toEqual(mockResponse)
    })

    it('propagates errors from API', async () => {
      const credentials = { email: 'test@test.com', password: 'wrong' }
      const error = new Error('Invalid credentials')
      api.post.mockRejectedValue(error)

      await expect(authApi.login(credentials)).rejects.toThrow('Invalid credentials')
    })

    it('handles network errors', async () => {
      const credentials = { email: 'test@test.com', password: 'password' }
      api.post.mockRejectedValue(new Error('Network Error'))

      await expect(authApi.login(credentials)).rejects.toThrow('Network Error')
    })
  })

  describe('register', () => {
    it('calls POST /auth/register with user data', async () => {
      const userData = {
        email: 'new@test.com',
        password: 'password123',
        full_name: 'Test User'
      }
      const mockResponse = { data: { user_id: 1, email: 'new@test.com' } }
      api.post.mockResolvedValue(mockResponse)

      const result = await authApi.register(userData)

      expect(api.post).toHaveBeenCalledWith('/auth/register', userData)
      expect(result).toEqual(mockResponse)
    })

    it('handles registration with all fields', async () => {
      const userData = {
        email: 'new@test.com',
        password: 'password123',
        full_name: 'Test User',
        role: 'operator',
        employee_id: 'EMP001'
      }
      api.post.mockResolvedValue({ data: { user_id: 1 } })

      await authApi.register(userData)

      expect(api.post).toHaveBeenCalledWith('/auth/register', userData)
    })

    it('handles duplicate email error', async () => {
      const userData = { email: 'existing@test.com', password: 'password' }
      api.post.mockRejectedValue(new Error('Email already exists'))

      await expect(authApi.register(userData)).rejects.toThrow('Email already exists')
    })
  })

  describe('getCurrentUser', () => {
    it('calls GET /auth/me', async () => {
      const mockResponse = { data: { user_id: 1, email: 'test@test.com' } }
      api.get.mockResolvedValue(mockResponse)

      const result = await authApi.getCurrentUser()

      expect(api.get).toHaveBeenCalledWith('/auth/me')
      expect(result).toEqual(mockResponse)
    })

    it('handles unauthorized error', async () => {
      api.get.mockRejectedValue(new Error('Unauthorized'))

      await expect(authApi.getCurrentUser()).rejects.toThrow('Unauthorized')
    })
  })

  describe('forgotPassword', () => {
    it('calls POST /auth/forgot-password with email', async () => {
      const email = 'user@test.com'
      const mockResponse = { data: { message: 'Reset email sent' } }
      api.post.mockResolvedValue(mockResponse)

      const result = await authApi.forgotPassword(email)

      expect(api.post).toHaveBeenCalledWith('/auth/forgot-password', { email })
      expect(result).toEqual(mockResponse)
    })

    it('handles non-existent email gracefully', async () => {
      const email = 'nonexistent@test.com'
      // API may still return success to prevent email enumeration
      const mockResponse = { data: { message: 'If email exists, reset link sent' } }
      api.post.mockResolvedValue(mockResponse)

      const result = await authApi.forgotPassword(email)

      expect(result.data.message).toContain('reset')
    })

    it('handles invalid email format', async () => {
      api.post.mockRejectedValue(new Error('Invalid email format'))

      await expect(authApi.forgotPassword('invalid-email')).rejects.toThrow('Invalid email format')
    })

    it('handles rate limiting', async () => {
      api.post.mockRejectedValue(new Error('Too many requests'))

      await expect(authApi.forgotPassword('user@test.com')).rejects.toThrow('Too many requests')
    })
  })

  describe('resetPassword', () => {
    it('calls POST /auth/reset-password with token and new password', async () => {
      const token = 'valid-reset-token'
      const newPassword = 'newSecurePassword123'
      const mockResponse = { data: { message: 'Password reset successful' } }
      api.post.mockResolvedValue(mockResponse)

      const result = await authApi.resetPassword(token, newPassword)

      expect(api.post).toHaveBeenCalledWith('/auth/reset-password', {
        token,
        new_password: newPassword
      })
      expect(result).toEqual(mockResponse)
    })

    it('handles expired token', async () => {
      api.post.mockRejectedValue(new Error('Token expired'))

      await expect(authApi.resetPassword('expired-token', 'newpass')).rejects.toThrow('Token expired')
    })

    it('handles invalid token', async () => {
      api.post.mockRejectedValue(new Error('Invalid token'))

      await expect(authApi.resetPassword('invalid-token', 'newpass')).rejects.toThrow('Invalid token')
    })

    it('handles weak password rejection', async () => {
      api.post.mockRejectedValue(new Error('Password does not meet requirements'))

      await expect(authApi.resetPassword('valid-token', 'weak')).rejects.toThrow('Password does not meet requirements')
    })
  })

  describe('verifyResetToken', () => {
    it('calls GET /auth/verify-reset-token/:token', async () => {
      const token = 'valid-token'
      const mockResponse = { data: { valid: true, email: 'user@test.com' } }
      api.get.mockResolvedValue(mockResponse)

      const result = await authApi.verifyResetToken(token)

      expect(api.get).toHaveBeenCalledWith(`/auth/verify-reset-token/${token}`)
      expect(result.data.valid).toBe(true)
    })

    it('handles invalid token verification', async () => {
      api.get.mockRejectedValue(new Error('Invalid or expired token'))

      await expect(authApi.verifyResetToken('bad-token')).rejects.toThrow('Invalid or expired token')
    })
  })

  describe('changePassword', () => {
    it('calls POST /auth/change-password with current and new password', async () => {
      const currentPassword = 'oldPassword123'
      const newPassword = 'newPassword456'
      const mockResponse = { data: { message: 'Password changed' } }
      api.post.mockResolvedValue(mockResponse)

      const result = await authApi.changePassword(currentPassword, newPassword)

      expect(api.post).toHaveBeenCalledWith('/auth/change-password', {
        current_password: currentPassword,
        new_password: newPassword
      })
      expect(result).toEqual(mockResponse)
    })

    it('handles incorrect current password', async () => {
      api.post.mockRejectedValue(new Error('Current password is incorrect'))

      await expect(authApi.changePassword('wrong', 'new')).rejects.toThrow('Current password is incorrect')
    })

    it('handles same password rejection', async () => {
      api.post.mockRejectedValue(new Error('New password must be different'))

      await expect(authApi.changePassword('same', 'same')).rejects.toThrow('New password must be different')
    })
  })

  describe('refreshToken', () => {
    it('calls POST /auth/refresh', async () => {
      const mockResponse = { data: { access_token: 'new-token' } }
      api.post.mockResolvedValue(mockResponse)

      const result = await authApi.refreshToken()

      expect(api.post).toHaveBeenCalledWith('/auth/refresh')
      expect(result.data.access_token).toBe('new-token')
    })

    it('handles refresh failure', async () => {
      api.post.mockRejectedValue(new Error('Refresh token expired'))

      await expect(authApi.refreshToken()).rejects.toThrow('Refresh token expired')
    })
  })

  describe('verifyEmail', () => {
    it('calls POST /auth/verify-email with token', async () => {
      const token = 'email-verification-token'
      const mockResponse = { data: { verified: true } }
      api.post.mockResolvedValue(mockResponse)

      const result = await authApi.verifyEmail(token)

      expect(api.post).toHaveBeenCalledWith('/auth/verify-email', { token })
      expect(result.data.verified).toBe(true)
    })

    it('handles invalid verification token', async () => {
      api.post.mockRejectedValue(new Error('Invalid verification token'))

      await expect(authApi.verifyEmail('bad-token')).rejects.toThrow('Invalid verification token')
    })
  })
})
