import api from './client'

export interface LoginCredentials {
  username: string
  password: string
}

export interface RegisterPayload {
  username: string
  email: string
  password: string
  full_name?: string
  role?: string
  client_id_assigned?: string | null
}

export const login = (credentials: LoginCredentials) => api.post('/auth/login', credentials)

export const register = (userData: RegisterPayload) => api.post('/auth/register', userData)

export const getCurrentUser = () => api.get('/auth/me')

export const forgotPassword = (email: string) => api.post('/auth/forgot-password', { email })

export const resetPassword = (token: string, newPassword: string) =>
  api.post('/auth/reset-password', { token, new_password: newPassword })

export const verifyResetToken = (token: string) => api.get(`/auth/verify-reset-token/${token}`)

export const changePassword = (currentPassword: string, newPassword: string) =>
  api.post('/auth/change-password', {
    current_password: currentPassword,
    new_password: newPassword,
  })

export const refreshToken = () => api.post('/auth/refresh')

export const verifyEmail = (token: string) => api.post('/auth/verify-email', { token })
