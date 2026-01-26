/**
 * Unit tests for Auth Store
 * Tests authentication state management, login, register, and logout actions
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '../authStore'

// Mock the API module
vi.mock('@/services/api', () => ({
  default: {
    login: vi.fn(),
    register: vi.fn()
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
  })
})
