import api from './client'

export const getProductionLines = (clientId: string) => {
  return api.get('/production-lines', { params: { client_id: clientId } })
}

export const getProductionLineTree = (clientId: string) => {
  return api.get('/production-lines/tree', { params: { client_id: clientId } })
}

export default {
  getProductionLines,
  getProductionLineTree,
}
