import React, { useEffect, useMemo, useState } from 'react'
import { Search, Filter, Upload, FileText } from 'lucide-react'
import FacturaModal from '../components/FacturaModal'
import { StatusBadge } from '../components/DashboardBase'
import {
  causarFactura,
  getAlegraCatalogo,
  getFacturas,
  isApiConfigured,
  previewFacturasUpload,
  uploadFacturas,
} from '../lib/api'
import { useToast } from '../components/ToastProvider'

const DEFAULT_PAGE_SIZE = 10

export default function Facturas() {
  const toast = useToast()
  const [filters, setFilters] = useState({ estado: '', proveedor: '', desde: '', hasta: '' })
  const [page, setPage] = useState(1)
  const [pageSize] = useState(DEFAULT_PAGE_SIZE)
  const [data, setData] = useState([])
  const [count, setCount] = useState(0)
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState(null)
  const [catalogo, setCatalogo] = useState({ categories: [], cost_centers: [] })
  const [causarLoading, setCausarLoading] = useState(false)
  const [error, setError] = useState(null)
  const [uploadFilesState, setUploadFilesState] = useState([])
  const [uploadApplyAi, setUploadApplyAi] = useState(true)
  const [uploadPreview, setUploadPreview] = useState(null)
  const [uploadPreviewLoading, setUploadPreviewLoading] = useState(false)
  const [uploadSaving, setUploadSaving] = useState(false)

  const getBackendErrorMessage = (err, fallback) => {
    const detail = err?.response?.data?.detail
    if (typeof detail === 'string' && detail.trim()) return detail
    if (detail && typeof detail === 'object' && typeof detail.message === 'string' && detail.message.trim()) {
      return detail.message
    }
    return fallback
  }

  const totalPages = useMemo(() => Math.max(1, Math.ceil(count / pageSize)), [count, pageSize])

  const buildUploadFormData = () => {
    const formData = new FormData()
    uploadFilesState.forEach((file) => formData.append('files', file))
    return formData
  }

  const fetchData = async () => {
    if (!isApiConfigured) { setError('VITE_API_URL no está configurado.'); return }
    setLoading(true)
    setError(null)
    try {
      const response = await getFacturas({
        page, page_size: pageSize,
        estado:    filters.estado    || undefined,
        proveedor: filters.proveedor || undefined,
        desde:     filters.desde     || undefined,
        hasta:     filters.hasta     || undefined,
      })
      setData(response.data.data  || [])
      setCount(response.data.count || 0)
    } catch {
      setError('No se pudo cargar la lista de facturas.')
      toast.error('No se pudo consultar facturas en este momento.')
    } finally {
      setLoading(false)
    }
  }

  const fetchCatalogo = async () => {
    if (!isApiConfigured) return
    try {
      const response = await getAlegraCatalogo()
      setCatalogo({
        categories:   response.data?.categories   || [],
        cost_centers: response.data?.cost_centers || [],
      })
    } catch {
      toast.warning('No se pudo cargar el catálogo de cuentas y centros.')
    }
  }

  const handleItemChange = (itemId, field, value) => {
    setSelected((prev) => {
      if (!prev) return prev
      const updatedItems = (prev.items_factura || []).map((item) =>
        String(item.id) === String(itemId) ? { ...item, [field]: value || null } : item
      )
      return { ...prev, items_factura: updatedItems }
    })
  }

  const handleCausar = async () => {
    if (!selected) return
    setCausarLoading(true)
    try {
      const itemOverrides = (selected.items_factura || []).map((item) => ({
        item_id:                item.id,
        cuenta_contable_alegra: item.cuenta_contable_alegra || null,
        centro_costo_alegra:    item.centro_costo_alegra    || null,
      }))
      await causarFactura(selected.id, { item_overrides: itemOverrides })
      await fetchData()
      setSelected(null)
      toast.success('Factura causada correctamente en Alegra.')
    } catch (err) {
      const msg = getBackendErrorMessage(err, 'No se pudo enviar a Alegra. Revisa la configuración.')
      setError(msg)
      toast.error(msg)
    } finally {
      setCausarLoading(false)
    }
  }

  const handlePreviewUpload = async () => {
    if (!uploadFilesState.length) { toast.warning('Selecciona al menos un XML o ZIP.'); return }
    setUploadPreviewLoading(true)
    try {
      const response = await previewFacturasUpload(buildUploadFormData(), uploadApplyAi)
      setUploadPreview(response.data || null)
      toast.success('Previsualización generada.')
    } catch (err) {
      toast.error(getBackendErrorMessage(err, 'No se pudo previsualizar la carga.'))
    } finally {
      setUploadPreviewLoading(false)
    }
  }

  const handleUploadFacturas = async () => {
    if (!uploadFilesState.length) { toast.warning('Selecciona al menos un XML o ZIP.'); return }
    setUploadSaving(true)
    try {
      const response = await uploadFacturas(buildUploadFormData(), uploadApplyAi)
      const s = response.data?.summary || {}
      toast.success(`Carga terminada: ${s.created || 0} creadas, ${s.duplicates || 0} duplicadas, ${s.errors || 0} con error.`)
      setUploadPreview(null)
      setUploadFilesState([])
      await fetchData()
      setPage(1)
    } catch (err) {
      toast.error(getBackendErrorMessage(err, 'No se pudo cargar facturas.'))
    } finally {
      setUploadSaving(false)
    }
  }

  useEffect(() => { fetchData(); fetchCatalogo() }, [page, filters])

  /* ------------------------------------------------------------------ */
  return (
    <div>
      {/* ── Page heading ──────────────────────────────────────────── */}
      <div className="page-heading">
        <div>
          <h1 className="page-heading-title">Control de Facturas</h1>
          <p className="page-heading-sub">Consulta completa y causación manual — {count} registro{count !== 1 ? 's' : ''}</p>
        </div>
      </div>

      {error && <div className="ui-alert" role="alert">{error}</div>}

      {/* ── Filtros ───────────────────────────────────────────────── */}
      <div className="sb-card">
        <div className="sb-card-header">
          <h2 className="sb-card-header-title" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <Filter size={14} /> Filtros
          </h2>
        </div>
        <div className="sb-card-body">
          <div className="filter-row">
            {/* Estado */}
            <div>
              <label htmlFor="filter-estado">Estado</label>
              <select
                id="filter-estado"
                className="input"
                value={filters.estado}
                onChange={(e) => { setPage(1); setFilters((p) => ({ ...p, estado: e.target.value })) }}
              >
                <option value="">Todos</option>
                <option value="pendiente">Pendiente</option>
                <option value="pendiente_revision">Pendiente revisión</option>
                <option value="procesado">Causado</option>
                <option value="error">Error</option>
                <option value="duplicado">Duplicado</option>
              </select>
            </div>

            {/* Proveedor */}
            <div>
              <label htmlFor="filter-proveedor">Proveedor</label>
              <div style={{ position: 'relative' }}>
                <Search
                  size={14}
                  style={{
                    position: 'absolute', left: '0.6rem',
                    top: '50%', transform: 'translateY(-50%)',
                    color: 'var(--muted)', pointerEvents: 'none',
                  }}
                />
                <input
                  id="filter-proveedor"
                  className="input"
                  style={{ paddingLeft: '2rem' }}
                  placeholder="Buscar proveedor…"
                  value={filters.proveedor}
                  onChange={(e) => { setPage(1); setFilters((p) => ({ ...p, proveedor: e.target.value })) }}
                />
              </div>
            </div>

            {/* Desde */}
            <div>
              <label htmlFor="filter-desde">Desde</label>
              <input
                id="filter-desde"
                type="date"
                className="input"
                value={filters.desde}
                onChange={(e) => { setPage(1); setFilters((p) => ({ ...p, desde: e.target.value })) }}
              />
            </div>

            {/* Hasta */}
            <div>
              <label htmlFor="filter-hasta">Hasta</label>
              <input
                id="filter-hasta"
                type="date"
                className="input"
                value={filters.hasta}
                onChange={(e) => { setPage(1); setFilters((p) => ({ ...p, hasta: e.target.value })) }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* ── Carga manual DIAN ────────────────────────────────────── */}
      <div className="sb-card">
        <div className="sb-card-header">
          <h2 className="sb-card-header-title" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <Upload size={14} /> Carga Manual DIAN (XML / ZIP)
          </h2>
          <span className="text-muted text-xs fw-bold">
            {uploadFilesState.length} archivo{uploadFilesState.length !== 1 ? 's' : ''} seleccionado{uploadFilesState.length !== 1 ? 's' : ''}
          </span>
        </div>
        <div className="sb-card-body">
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr auto auto',
              gap: '0.75rem',
              alignItems: 'end',
            }}
            className="upload-row"
          >
            <div>
              <label htmlFor="upload-files">Archivos XML / ZIP</label>
              <input
                id="upload-files"
                type="file"
                multiple
                accept=".xml,.zip"
                className="input"
                onChange={(e) => setUploadFilesState(Array.from(e.target.files || []))}
              />
            </div>

            <label
              style={{
                display: 'flex', alignItems: 'center', gap: '0.4rem',
                fontWeight: 700, fontSize: '0.82rem', textTransform: 'none',
                letterSpacing: 0, color: 'var(--text)', cursor: 'pointer',
                paddingBottom: '0.25rem',
              }}
            >
              <input
                type="checkbox"
                checked={uploadApplyAi}
                onChange={(e) => setUploadApplyAi(e.target.checked)}
              />
              Aplicar IA
            </label>

            <div style={{ display: 'flex', gap: '0.5rem', paddingBottom: '0.1rem' }}>
              <button
                className="btn-secondary btn-sm"
                onClick={handlePreviewUpload}
                disabled={uploadPreviewLoading || uploadSaving}
              >
                {uploadPreviewLoading ? 'Previsualizando…' : 'Previsualizar'}
              </button>
              <button
                className="btn-primary btn-sm"
                onClick={handleUploadFacturas}
                disabled={uploadSaving || uploadPreviewLoading}
              >
                {uploadSaving ? 'Cargando…' : 'Cargar facturas'}
              </button>
            </div>
          </div>

          {/* Upload preview table */}
          {uploadPreview && (
            <div style={{ marginTop: '1rem' }}>
              <div
                className="text-sm fw-bold text-muted"
                style={{ marginBottom: '0.5rem' }}
              >
                Previsualización — {uploadPreview.summary?.valid || 0} válidas,{' '}
                {uploadPreview.summary?.duplicates || 0} duplicadas,{' '}
                {uploadPreview.summary?.invalid || 0} inválidas
              </div>
              <div className="table-responsive" style={{ borderRadius: '0.375rem', border: '1px solid var(--border)' }}>
                <table className="table-admin">
                  <thead>
                    <tr>
                      <th>Archivo</th>
                      <th>Factura</th>
                      <th>Proveedor</th>
                      <th>Estado</th>
                      <th>Detalle</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(uploadPreview.files || []).map((entry, idx) => (
                      <tr key={`${entry.file_name || 'f'}-${idx}`}>
                        <td className="text-sm">{entry.entry_name || entry.file_name || '—'}</td>
                        <td className="text-sm fw-bold">{entry.factura_preview?.numero_factura || '—'}</td>
                        <td className="text-sm">{entry.factura_preview?.nombre_proveedor || '—'}</td>
                        <td><StatusBadge status={entry.status || 'pendiente'} /></td>
                        <td className="text-sm text-muted">{entry.reason || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── Tabla de facturas ────────────────────────────────────── */}
      <div className="sb-card">
        <div className="sb-card-header">
          <h2 className="sb-card-header-title" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <FileText size={14} /> Facturas Registradas
          </h2>
        </div>

        <div className="table-responsive">
          <table className="table-admin" aria-label="Lista de facturas">
            <thead>
              <tr>
                <th>Factura</th>
                <th>Proveedor</th>
                <th className="d-none-mobile">NIT</th>
                <th>Total</th>
                <th>Estado</th>
                <th className="d-none-mobile">Fecha</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td colSpan={6}>
                    <div className="table-empty">
                      <div className="table-empty-icon">⏳</div>
                      <p className="fw-bold">Cargando facturas…</p>
                    </div>
                  </td>
                </tr>
              )}

              {!loading && data.map((row) => (
                <tr
                  key={row.id}
                  onClick={() => setSelected(row)}
                  style={{ cursor: 'pointer' }}
                >
                  <td>
                    <span style={{ color: 'var(--accent)', fontWeight: 700 }}>
                      {row.numero_factura}
                    </span>
                  </td>
                  <td>{row.nombre_proveedor}</td>
                  <td className="d-none-mobile text-muted">{row.nit_proveedor || '—'}</td>
                  <td className="fw-bold">${Number(row.total || 0).toLocaleString('es-CO')}</td>
                  <td><StatusBadge status={row.estado} /></td>
                  <td className="d-none-mobile text-muted">
                    {new Date(row.created_at).toLocaleDateString('es-CO', {
                      day: '2-digit', month: 'short', year: 'numeric',
                    })}
                  </td>
                </tr>
              ))}

              {!loading && data.length === 0 && (
                <tr>
                  <td colSpan={6}>
                    <div className="table-empty">
                      <div className="table-empty-icon">🗂️</div>
                      <p className="fw-bold">No hay facturas para los filtros actuales</p>
                      <p className="text-sm text-muted mt-1">Ajusta los filtros o carga nuevas facturas.</p>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination in card footer */}
        <div className="table-footer">
          <span className="text-sm text-muted">
            Página <strong>{page}</strong> de <strong>{totalPages}</strong>
            {' '}— <strong>{count}</strong> registro{count !== 1 ? 's' : ''}
          </span>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              className="btn-secondary btn-sm"
              disabled={page === 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              ← Anterior
            </button>
            <button
              className="btn-secondary btn-sm"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            >
              Siguiente →
            </button>
          </div>
        </div>
      </div>

      {/* ── Modal ────────────────────────────────────────────────── */}
      <FacturaModal
        factura={selected}
        onItemChange={handleItemChange}
        onClose={() => setSelected(null)}
        onCausar={handleCausar}
        loading={causarLoading}
        categories={catalogo.categories}
        costCenters={catalogo.cost_centers}
      />
    </div>
  )
}
