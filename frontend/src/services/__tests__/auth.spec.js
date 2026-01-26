/**
 * Unit tests for Auth API module
 * Tests authentication API calls
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
  })

  describe('getCurrentUser', () => {
    it('calls GET /auth/me', async () => {
      const mockResponse = { data: { user_id: 1, email: 'test@test.com' } }
      api.get.mockResolvedValue(mockResponse)

      const result = await authApi.getCurrentUser()

      expect(api.get).toHaveBeenCalledWith('/auth/me')
      expect(result).toEqual(mockResponse)
    })
  })
})
