import api from './client'

export const getProductionLines = (clientId: string) => {
  // Trailing slash matches the backend's APIRouter("/") definition. Without
  // it, FastAPI returns a 307 redirect — and axios drops the Authorization
  // header on redirects, which would 401 the redirected request and trigger
  // the response interceptor's logout flow.
  return api.get('/production-lines/', { params: { client_id: clientId } })
}

export const getProductionLineTree = (clientId: string) => {
  return api.get('/production-lines/tree', { params: { client_id: clientId } })
}

export default {
  getProductionLines,
  getProductionLineTree,
}
