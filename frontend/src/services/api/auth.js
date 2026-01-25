import api from './client'

export const login = (credentials) => api.post('/auth/login', credentials)

export const register = (userData) => api.post('/auth/register', userData)

export const getCurrentUser = () => api.get('/auth/me')
