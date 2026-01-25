import api from './client'

export const getProducts = () => api.get('/products')

export const getShifts = () => api.get('/shifts')

export const getDowntimeReasons = () => api.get('/downtime-reasons')
