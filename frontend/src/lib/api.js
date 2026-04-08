import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL

export const api = axios.create({
  baseURL: API_URL ? `${API_URL}/api` : undefined,
})

export const getFacturas = (params) => api.get('/facturas', { params })
export const getFacturaById = (id) => api.get(`/facturas/${id}`)
export const causarFactura = (id, payload) => api.post(`/facturas/${id}/causar`, payload)
export const getFacturasStats = () => api.get('/facturas/stats')

export const getConfigCuentas = (params) => api.get('/config', { params })
export const getAlegraCatalogo = (params) => api.get('/config/alegra/catalogo', { params })
export const createConfigCuenta = (payload) => api.post('/config', payload)
export const updateConfigCuenta = (id, payload) => api.patch(`/config/${id}`, payload)
export const deleteConfigCuenta = (id) => api.delete(`/config/${id}`)

export const getLogs = (params) => api.get('/logs', { params })

export const getProcesoStatus = () => api.get('/proceso/status')
export const triggerProcesoManual = () => api.post('/proceso/manual')

export const isApiConfigured = Boolean(API_URL)
