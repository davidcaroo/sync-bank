import React, { useEffect, useMemo, useState, useRef } from 'react'
import {
  IconSearch,
  IconFilter,
  IconUpload,
  IconFileText,
  IconFolder,
  IconX,
  IconLoading,
  IconArchive
} from '../components/icons/Icons'
import FacturaModal from '../components/FacturaModal'
import { StatusBadge } from '../components/DashboardBase'
import {
  causarFactura,
  getAlegraCatalogo,
  getFacturaById,
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
  const [showUploadModal, setShowUploadModal] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef(null)

  const getBackendErrorMessage = (err, fallback) => {
    const detail = err?.response?.data?.detail
    if (typeof detail === 'string' && detail.trim()) return detail
    if (detail && typeof detail === 'object' && typeof detail.message === 'string' && detail.message.trim()) {
      return detail.message
    }
    return fallback
  }

  const buildCausarNotification = (err) => {
    const status = Number(err?.response?.status || 0)
    const msg = getBackendErrorMessage(err, 'No se pudo enviar a Alegra. Revisa la configuración.')
    const code = err?.response?.data?.detail?.code

    if (code === 'DUPLICADO_ALEGRA' || code === 'FACTURA_YA_CAUSADA') {
      return { kind: 'warning', message: msg, code }
    }

    if (code === 'NO_VERIFICADO_ALEGRA') {
      return {
        kind: 'warning',
        code,
        message: 'No se pudo confirmar en Alegra si la factura aún existe. Intenta de nuevo en unos segundos.',
      }
    }

    if (
      status === 502
      && msg.includes('No se pudo encontrar ni crear el proveedor')
      && msg.toLowerCase().includes('ya existe un contacto con la identificacion')
    ) {
      return {
        kind: 'error',
        code,
        message: 'Alegra rechazó la causación porque el NIT ya existe como contacto y no se pudo resolver automáticamente como proveedor. Verifica el contacto en Alegra y vuelve a intentar.',
      }
    }

    if (status === 502) {
      if (msg.toLowerCase().includes('no se encontro un impuesto activo en alegra para iva')) {
        return {
          kind: 'error',
          code,
          message: 'No se pudo causar la factura porque en Alegra no hay un impuesto IVA activo con ese porcentaje. Revisa el catálogo de impuestos en Alegra.',
        }
      }
      return {
        kind: 'error',
        code,
        message: `Error de integración con Alegra: ${msg}`,
      }
    }

    return { kind: 'error', message: msg, code }
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

  const handleSelectFactura = async (row) => {
    setSelected(row)
    try {
      const response = await getFacturaById(row.id)
      const enriched = response?.data
      if (enriched) {
        setSelected(enriched)
        setData((prev) => (prev || []).map((item) => (item.id === row.id ? { ...item, ...enriched } : item)))
      }
    } catch {
      toast.warning('No se pudo enriquecer el detalle desde Alegra. Se muestra la info local.')
    }
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
      const notification = buildCausarNotification(err)
      const code = notification.code
      if (code === 'DUPLICADO_ALEGRA' || code === 'FACTURA_YA_CAUSADA') {
        toast.warning(notification.message)
        await fetchData()
        if (selected?.id) {
          try {
            const response = await getFacturaById(selected.id)
            if (response?.data) {
              setSelected(response.data)
            }
          } catch {
            // Best effort refresh after duplicate in Alegra
          }
        }
      } else {
        setError(notification.message)
        if (notification.kind === 'warning') {
          toast.warning(notification.message)
        } else {
          toast.error(notification.message)
        }
      }
    } finally {
      setCausarLoading(false)
    }
  }

  const handlePreviewUpload = async () => {
    if (!uploadFilesState.length) { toast.warning('Selecciona al menos un XML o ZIP.'); return }
    setUploadPreviewLoading(true)
    try {
      const response = await previewFacturasUpload(buildUploadFormData(), uploadApplyAi)
      const payload = response.data || null
      setUploadPreview(payload)

      const summary = payload?.summary || {}
      const totalXml = Number(summary.total_xml || 0)
      const invalid = Number(summary.invalid || 0)

      if (totalXml === 0 && invalid === 0) {
        toast.warning('No se detectaron XML dentro de los ZIP seleccionados.')
      } else {
        toast.success('Previsualización generada.')
      }
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
      const totalXml = Number(s.total_xml || 0)
      if (totalXml === 0) {
        toast.warning('No se cargaron facturas: no se encontraron XML procesables en los archivos.')
      } else {
        toast.success(`Carga terminada: ${s.created || 0} creadas, ${s.duplicates || 0} duplicadas, ${s.errors || 0} con error.`)
      }
      setUploadPreview(null)
      setUploadFilesState([])
      setShowUploadModal(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
      await fetchData()
      setPage(1)
    } catch (err) {
      toast.error(getBackendErrorMessage(err, 'No se pudo cargar facturas.'))
    } finally {
      setUploadSaving(false)
    }
  }

  useEffect(() => { fetchData(); fetchCatalogo() }, [page, filters])

  useEffect(() => {
    const fn = (e) => e.key === 'Escape' && setShowUploadModal(false)
    document.addEventListener('keydown', fn)
    return () => document.removeEventListener('keydown', fn)
  }, [])

  const handleFilesSelected = (files) => {
    const validFiles = Array.from(files).filter(f => f.name.toLowerCase().endsWith('.xml') || f.name.toLowerCase().endsWith('.zip'))
    setUploadFilesState(validFiles)
  }

  const handleCloseModal = () => {
    setShowUploadModal(false)
    setUploadFilesState([])
    setUploadPreview(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  /* ------------------------------------------------------------------ */
  return (
    <div>
      {/* ── Page heading ──────────────────────────────────────────── */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        marginBottom: '24px'
      }}>
        <div>
          <h1 className="page-heading-title">Control de Facturas</h1>
          <p className="page-heading-sub">
            Consulta completa y causación manual — {count} registro{count !== 1 ? 's' : ''}
          </p>
        </div>
        <button
          onClick={() => setShowUploadModal(true)}
          style={{
            background: '#d4edda',
            color: '#155724',
            border: '1.5px solid #c3e6cb',
            borderRadius: '8px',
            padding: '10px 20px',
            fontWeight: 700,
            fontSize: '0.875rem',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            transition: 'all 0.15s ease'
          }}
          onMouseEnter={e => {
            e.currentTarget.style.background = '#c3e6cb'
            e.currentTarget.style.borderColor = '#b1dfbb'
          }}
          onMouseLeave={e => {
            e.currentTarget.style.background = '#d4edda'
            e.currentTarget.style.borderColor = '#c3e6cb'
          }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" 
               stroke="currentColor" strokeWidth="2.5">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="17 8 12 3 7 8"/>
            <line x1="12" y1="3" x2="12" y2="15"/>
          </svg>
          Cargar Facturas XML
        </button>
      </div>

      {error && <div className="ui-alert" role="alert">{error}</div>}

      {/* ── Filtros ───────────────────────────────────────────────── */}
      <div className="sb-card">
        <div className="sb-card-header">
          <h2 className="sb-card-header-title" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <IconFilter size={14} /> Filtros
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
                <IconSearch
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


      {/* ── Tabla de facturas ────────────────────────────────────── */}
      <div className="sb-card">
        <div className="sb-card-header">
          <h2 className="sb-card-header-title" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <IconFileText size={14} /> Facturas Registradas
          </h2>
        </div>

        <div className="table-responsive">
          <table className="table-admin" aria-label="Lista de facturas">
            <thead>
              <tr>
                <th>Factura</th>
                <th>Proveedor</th>
                <th className="d-none-mobile">NIT</th>
                <th>Total a pagar</th>
                <th>Estado</th>
                <th className="d-none-mobile">Fecha</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td colSpan={6}>
                    <div style={{ textAlign: 'center', padding: '48px 24px', color: '#b7b9cc' }}>
                      <IconLoading size={48} color="#b7b9cc" style={{
                        animation: 'spin 1s linear infinite'
                      }}/>
                      <p style={{ marginTop: '16px', color: '#858796', fontSize: '0.9rem', fontWeight: 600 }}>
                        Cargando facturas...
                      </p>
                    </div>
                  </td>
                </tr>
              )}

              {!loading && data.map((row) => (
                <tr
                  key={row.id}
                  onClick={() => handleSelectFactura(row)}
                  style={{ cursor: 'pointer' }}
                >
                  <td>
                    <span style={{ color: 'var(--accent)', fontWeight: 700 }}>
                      {row.numero_factura}
                    </span>
                  </td>
                  <td>{row.nombre_proveedor}</td>
                  <td className="d-none-mobile text-muted">{row.nit_proveedor || '—'}</td>
                  <td className="fw-bold">${Number(row.total_neto || row.total || 0).toLocaleString('es-CO')}</td>
                  <td><StatusBadge status={row.estado} /></td>
                  <td className="d-none-mobile text-muted">
                    {new Date(row.created_at).toLocaleDateString('es-CO', {
                      day: '2-digit', month: 'short', year: 'numeric',
                      timeZone: 'America/Bogota',
                    })}
                  </td>
                </tr>
              ))}

              {!loading && data.length === 0 && (
                <tr>
                  <td colSpan={6}>
                    <div className="table-empty">
                      <div className="table-empty-icon" style={{ opacity: 0.2 }}>
                        <IconArchive size={48} />
                      </div>
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

      {/* ── Modal Carga Manual DIAN ──────────────────────────────── */}
      {showUploadModal && (
        <div style={{
          position: 'fixed', inset: 0,
          background: 'rgba(0,0,0,0.5)',
          zIndex: 1050,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '16px'
        }}
        onClick={(e) => e.target === e.currentTarget && handleCloseModal()}
        >
          <div style={{
            background: 'white',
            borderRadius: '12px',
            width: '100%',
            maxWidth: '600px',
            maxHeight: '90vh',
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
            boxShadow: '0 10px 40px rgba(0,0,0,0.2)'
          }}>

            {/* HEADER */}
            <div style={{
              padding: '20px 24px',
              borderBottom: '1px solid #e3e6f0',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}>
              <div>
                <h5 style={{ margin: 0, fontWeight: 700, color: '#5a5c69', fontSize: '1.1rem' }}>
                  Cargar Facturas DIAN
                </h5>
                <p style={{ margin: '2px 0 0', fontSize: '0.8rem', color: '#858796' }}>
                  Archivos XML individuales o ZIP con múltiples facturas
                </p>
              </div>
              <button onClick={handleCloseModal} style={{
                background: 'none', border: 'none', cursor: 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                padding: '4px', borderRadius: '4px'
              }}>
                <IconX size={20} color="#858796" />
              </button>
            </div>

            {/* BODY — scrollable */}
            <div style={{ padding: '24px', overflowY: 'auto', flex: 1 }}>

              {/* ZONA DRAG & DROP */}
              <div
                onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => {
                  e.preventDefault()
                  setDragOver(false)
                  handleFilesSelected(e.dataTransfer.files)
                }}
                style={{
                  border: `2px dashed ${dragOver ? '#4e73df' : '#d1d3e2'}`,
                  borderRadius: '10px',
                  padding: '40px 24px',
                  textAlign: 'center',
                  background: dragOver ? '#f0f4ff' : '#fafbfc',
                  transition: 'all 0.2s ease',
                  cursor: 'pointer',
                  marginBottom: '20px'
                }}
                onClick={() => fileInputRef.current?.click()}
              >
                <div style={{ marginBottom: '16px', opacity: 0.3 }}>
                  <IconFolder size={48} color="currentColor" />
                </div>
                <p style={{ fontWeight: 700, color: '#5a5c69', margin: '0 0 4px' }}>
                  Arrastra archivos aquí o haz clic para seleccionar
                </p>
                <p style={{ fontSize: '0.8rem', color: '#858796', margin: 0 }}>
                  Formatos aceptados: .xml, .zip — Múltiples archivos permitidos
                </p>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".xml,.zip"
                  multiple
                  style={{ display: 'none' }}
                  onChange={(e) => handleFilesSelected(e.target.files)}
                />
              </div>

              {/* LISTA DE ARCHIVOS SELECCIONADOS */}
              {uploadFilesState.length > 0 && (
                <div style={{
                  background: '#f8f9fc',
                  borderRadius: '8px',
                  padding: '12px 16px',
                  marginBottom: '20px'
                }}>
                  <p style={{
                    fontSize: '0.7rem', fontWeight: 800, textTransform: 'uppercase',
                    letterSpacing: '0.05em', color: '#858796', margin: '0 0 8px'
                  }}>
                    {uploadFilesState.length} archivo(s) seleccionado(s)
                  </p>
                  {uploadFilesState.map((file, i) => (
                    <div key={i} style={{
                      display: 'flex', justifyContent: 'space-between',
                      alignItems: 'center', padding: '6px 0',
                      borderBottom: i < uploadFilesState.length - 1 
                        ? '1px solid #e3e6f0' : 'none'
                    }}>
                      <span style={{ fontSize: '0.8rem', color: '#5a5c69', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <IconFileText size={14} color="#858796" />
                        {file.name}
                      </span>
                      <span style={{ fontSize: '0.75rem', color: '#858796' }}>
                        {(file.size / 1024).toFixed(1)} KB
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {/* OPCIONES */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '12px 16px',
                background: '#f8f9fc',
                borderRadius: '8px',
                border: '1px solid #e3e6f0'
              }}>
                <input
                  type="checkbox"
                  id="aplicarIA"
                  checked={uploadApplyAi}
                  onChange={(e) => setUploadApplyAi(e.target.checked)}
                  style={{ width: '16px', height: '16px', cursor: 'pointer' }}
                />
                <label htmlFor="aplicarIA" style={{
                  fontSize: '0.875rem', fontWeight: 600,
                  color: '#5a5c69', cursor: 'pointer', margin: 0
                }}>
                  Aplicar IA para clasificación automática de cuentas
                </label>
                <span style={{
                  marginLeft: 'auto',
                  fontSize: '0.7rem',
                  background: '#e8f4f8',
                  color: '#36b9cc',
                  padding: '2px 8px',
                  borderRadius: '20px',
                  fontWeight: 700
                }}>
                  RECOMENDADO
                </span>
              </div>

              {/* RESULTADO DE PREVISUALIZACIÓN */}
              {uploadPreview && (
                <div style={{ marginTop: '20px' }}>
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

            {/* FOOTER */}
            <div style={{
              padding: '16px 24px',
              borderTop: '1px solid #e3e6f0',
              display: 'flex',
              justifyContent: 'flex-end',
              gap: '12px',
              background: '#fafbfc'
            }}>
              <button
                onClick={handleCloseModal}
                style={{
                  background: 'white', color: '#858796',
                  border: '1px solid #d1d3e2', borderRadius: '6px',
                  padding: '8px 20px', fontWeight: 600,
                  fontSize: '0.875rem', cursor: 'pointer'
                }}
              >
                Cancelar
              </button>
              <button
                onClick={handlePreviewUpload}
                disabled={uploadFilesState.length === 0 || uploadPreviewLoading || uploadSaving}
                style={{
                  background: (uploadFilesState.length === 0 || uploadPreviewLoading || uploadSaving) ? '#f8f9fc' : 'white',
                  color: (uploadFilesState.length === 0 || uploadPreviewLoading || uploadSaving) ? '#b7b9cc' : '#4e73df',
                  border: `1px solid ${(uploadFilesState.length === 0 || uploadPreviewLoading || uploadSaving) ? '#e3e6f0' : '#4e73df'}`,
                  borderRadius: '6px', padding: '8px 20px',
                  fontWeight: 600, fontSize: '0.875rem',
                  cursor: (uploadFilesState.length === 0 || uploadPreviewLoading || uploadSaving) ? 'not-allowed' : 'pointer'
                }}
              >
                {uploadPreviewLoading ? 'Procesando…' : 'Previsualizar'}
              </button>
              <button
                onClick={handleUploadFacturas}
                disabled={uploadFilesState.length === 0 || uploadSaving || uploadPreviewLoading}
                style={{
                  background: (uploadFilesState.length === 0 || uploadSaving || uploadPreviewLoading) ? '#b7b9cc' : '#4e73df',
                  color: 'white', border: 'none', borderRadius: '6px',
                  padding: '8px 20px', fontWeight: 700,
                  fontSize: '0.875rem',
                  cursor: (uploadFilesState.length === 0 || uploadSaving || uploadPreviewLoading) ? 'not-allowed' : 'pointer'
                }}
              >
                {uploadSaving ? 'Cargando…' : 'Cargar Facturas'}
              </button>
            </div>

          </div>
        </div>
      )}
    </div>
  )
}
