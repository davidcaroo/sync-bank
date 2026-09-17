import axios from 'axios'
import { FACTURAS_COLLECTION, CONTACTOS_COLLECTION, CONFIG_COLLECTION, LOGS_COLLECTION } from './endpoints'

const API_URL = import.meta.env.VITE_API_URL

export const api = axios.create({
  baseURL: API_URL ? `${API_URL}/api` : '/api',
})

export const getFacturas = (params) => api.get(FACTURAS_COLLECTION, { params })
export const getFacturaById = (id) => api.get(`/facturas/${id}`)
export const causarFactura = (id, payload) => api.post(`/facturas/${id}/causar`, payload)
export const getFacturasStats = () => api.get('/facturas/stats')
export const previewFacturasUpload = (formData, applyAi = true) => api.post(`/facturas/preview-upload?apply_ai=${applyAi}`, formData, {
  headers: { 'Content-Type': 'multipart/form-data' },
})
export const uploadFacturas = (formData, applyAi = true) => api.post(`/facturas/upload?apply_ai=${applyAi}`, formData, {
  headers: { 'Content-Type': 'multipart/form-data' },
})
export const extraerPdf = (formData, preview = true) => api.post(`/facturas/extraer-pdf?preview=${preview}`, formData, {
  headers: { 'Content-Type': 'multipart/form-data' },
})
export const previewPdfFacturas = (payload) => api.post('/facturas/preview-pdf', payload)
export const confirmarPdfFacturas = (payload) => api.post('/facturas/confirmar-pdf', payload)

export const getConfigCuentas = (params) => api.get(CONFIG_COLLECTION, { params })
export const getAlegraCatalogo = (params) => api.get('/config/alegra/catalogo', { params })
export const createConfigCuenta = (payload) => api.post(CONFIG_COLLECTION, payload)
export const updateConfigCuenta = (id, payload) => api.patch(`/config/${id}`, payload)
export const deleteConfigCuenta = (id) => api.delete(`/config/${id}`)

export const getLogs = (params) => api.get(LOGS_COLLECTION, { params })

export const getContactos = (params) => api.get(CONTACTOS_COLLECTION, { params })
export const getContactoById = (id) => api.get(`/contactos/${id}`)
export const createContacto = (payload) => api.post(CONTACTOS_COLLECTION, payload)
export const updateContacto = (id, payload) => api.patch(`/contactos/${id}`, payload)
export const deleteContacto = (id) => api.delete(`/contactos/${id}`)

export const getProcesoStatus = () => api.get('/proceso/status')
export const triggerProcesoManual = () => api.post('/proceso/manual')

export const isApiConfigured = true
