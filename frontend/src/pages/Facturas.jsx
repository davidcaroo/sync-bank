import React, { useEffect, useMemo, useState, useRef } from 'react'
import {
  IconSearch,
  IconFilter,
  IconUpload,
  IconFileText,
  IconFolder,
  IconX,
  IconArchive
} from '../components/icons/Icons'
import FacturaModal from '../components/FacturaModal'
import { StatusBadge } from '../components/DashboardBase'
import {
  causarFactura,
  confirmarPdfFacturas,
  extraerPdf,
  getAlegraCatalogo,
  getFacturaById,
  getFacturas,
  isApiConfigured,
  previewFacturasUpload,
  previewPdfFacturas,
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
  const [uploadMode, setUploadMode] = useState('xml')
  const [pdfFile, setPdfFile] = useState(null)
  const [uploadPreview, setUploadPreview] = useState(null)
  const [uploadPreviewLoading, setUploadPreviewLoading] = useState(false)
  const [uploadSaving, setUploadSaving] = useState(false)
  const [pdfPreview, setPdfPreview] = useState(null)
  const [pdfPreviewLoading, setPdfPreviewLoading] = useState(false)
  const [pdfConfirming, setPdfConfirming] = useState(false)
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

  const buildPdfFormData = () => {
    const formData = new FormData()
    if (pdfFile) {
      formData.append('file', pdfFile)
    }
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
    if (!selected || causarLoading) return
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
      const response = await previewFacturasUpload(buildUploadFormData(), false)
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

  const handlePreviewPdf = async () => {
    if (!pdfFile) {
      toast.warning('Selecciona un PDF.');
      return
    }
    setPdfPreviewLoading(true)
    try {
      const extraction = await extraerPdf(buildPdfFormData(), true)
      const extractedFacturas = extraction?.data?.facturas || []
      if (!extractedFacturas.length) {
        setPdfPreview({ extraction: extraction?.data, preview: null })
        toast.warning('No se detectaron facturas en el PDF.')
        return
      }
      const previewResponse = await previewPdfFacturas({
        facturas: extractedFacturas,
        apply_ai: false,
        auto_apply_ai: false,
      })
      setPdfPreview({ extraction: extraction?.data, preview: previewResponse?.data })
      toast.success('Previsualización PDF generada.')
    } catch (err) {
      toast.error(getBackendErrorMessage(err, 'No se pudo previsualizar el PDF.'))
    } finally {
      setPdfPreviewLoading(false)
    }
  }

  const handleConfirmPdf = async () => {
    const extractedFacturas = pdfPreview?.extraction?.facturas || []
    if (!extractedFacturas.length) {
      toast.warning('No hay facturas para confirmar.')
      return
    }
    setPdfConfirming(true)
    try {
      const response = await confirmarPdfFacturas({
        facturas: extractedFacturas,
        apply_ai: false,
        auto_apply_ai: false,
      })
      const summary = response?.data?.summary || {}
      toast.success(`Carga PDF: ${summary.created || 0} creadas, ${summary.duplicates || 0} duplicadas, ${summary.errors || 0} con error.`)
      setPdfPreview(null)
      setPdfFile(null)
      setShowUploadModal(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
      await fetchData()
      setPage(1)
    } catch (err) {
      toast.error(getBackendErrorMessage(err, 'No se pudo confirmar el PDF.'))
    } finally {
      setPdfConfirming(false)
    }
  }

  const handleUploadFacturas = async () => {
    if (!uploadFilesState.length) { toast.warning('Selecciona al menos un XML o ZIP.'); return }
    setUploadSaving(true)
    try {
      const response = await uploadFacturas(buildUploadFormData(), false)
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

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { fetchData(); fetchCatalogo() }, [page, filters])

  useEffect(() => {
    const fn = (e) => e.key === 'Escape' && setShowUploadModal(false)
    document.addEventListener('keydown', fn)
    return () => document.removeEventListener('keydown', fn)
  }, [])

  const handleFilesSelected = (files) => {
    if (uploadMode === 'pdf') {
      const pdf = Array.from(files).find(f => f.name.toLowerCase().endsWith('.pdf'))
      setPdfFile(pdf || null)
      return
    }
    const validFiles = Array.from(files).filter(f => f.name.toLowerCase().endsWith('.xml') || f.name.toLowerCase().endsWith('.zip'))
    setUploadFilesState(validFiles)
  }

  const handleCloseModal = () => {
    setShowUploadModal(false)
    setUploadFilesState([])
    setUploadPreview(null)
    setPdfFile(null)
    setPdfPreview(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const handleModeChange = (mode) => {
    setUploadMode(mode)
    setUploadFilesState([])
    setUploadPreview(null)
    setPdfFile(null)
    setPdfPreview(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const normalizePreviewSource = (source) => {
    if (source === 'config') return 'Configuración'
    if (source === 'historical') return 'Historial'
    if (source === 'none') return 'Sin sugerencia'
    return source || 'Sin sugerencia'
  }

  const buildPreviewSuggestionText = (item) => {
    const cuenta = item?.cuenta_contable_alegra || item?.suggested_cuenta_contable_alegra || '—'
    const centro = item?.centro_costo_alegra || item?.suggested_centro_costo_alegra || '—'
    const source = normalizePreviewSource(item?.prefill_source)
    const confidence = item?.confidence
    const confidenceText = typeof confidence === 'number' ? `${Math.round(confidence * 100)}%` : '—'
    return {
      cuenta,
      centro,
      source,
      confidenceText,
      descripcion: item?.descripcion || 'Ítem sin descripción',
    }
  }

  /* ------------------------------------------------------------------ */
  return (
    <div className="page-shell">
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
        <button className="btn-primary" onClick={() => setShowUploadModal(true)}>
          <IconUpload size={16} />
          Cargar facturas
        </button>
      </div>

      {error && (
        <div className="ui-alert" role="alert">
          <div><strong>No pudimos cargar las facturas.</strong><span>{error}</span></div>
          <button type="button" className="btn-secondary btn-sm" onClick={fetchData}>Reintentar</button>
        </div>
      )}

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
                Array.from({ length: 6 }).map((_, index) => (
                  <tr key={`loading-${index}`} aria-hidden="true">
                    <td><span className="skeleton skeleton-line skeleton-line-short" /></td>
                    <td><span className="skeleton skeleton-line" /></td>
                    <td className="d-none-mobile"><span className="skeleton skeleton-line" /></td>
                    <td><span className="skeleton skeleton-line skeleton-line-short" /></td>
                    <td><span className="skeleton skeleton-chip" /></td>
                    <td className="d-none-mobile"><span className="skeleton skeleton-line" /></td>
                  </tr>
                ))
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
        <div
          className="modal-backdrop"
          onClick={(e) => e.target === e.currentTarget && handleCloseModal()}
          role="dialog"
          aria-modal="true"
          aria-label="Cargar facturas"
        >
          <div className="modal-box">
            {/* HEADER */}
            <div className="modal-header">
              <div>
                <h3 className="modal-header-title">Cargar facturas (XML o PDF)</h3>
                <p className="text-sm text-muted" style={{ marginTop: '0.1rem' }}>
                  XML/ZIP para DIAN y PDF para extracción asistida
                </p>
              </div>
              <button onClick={handleCloseModal} className="icon-btn" aria-label="Cerrar modal">
                <IconX size={16} />
              </button>
            </div>

            {/* BODY — scrollable */}
            <div className="modal-body">

              {/* SELECTOR DE MODO */}
              <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
                <button
                  onClick={() => handleModeChange('xml')}
                  className={uploadMode === 'xml' ? 'btn-primary' : 'btn-secondary'}
                  style={{ flex: 1, justifyContent: 'center' }}
                >
                  XML / ZIP DIAN
                </button>
                <button
                  onClick={() => handleModeChange('pdf')}
                  className={uploadMode === 'pdf' ? 'btn-primary' : 'btn-secondary'}
                  style={{ flex: 1, justifyContent: 'center' }}
                >
                  PDF (texto + OCR)
                </button>
              </div>

              {/* ZONA DRAG & DROP */}
              <div
                onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => {
                  e.preventDefault()
                  setDragOver(false)
                  handleFilesSelected(e.dataTransfer.files)
                }}
                onClick={() => fileInputRef.current?.click()}
                style={{
                  border: `2px dashed ${dragOver ? 'var(--accent)' : 'var(--border)'}`,
                  borderRadius: '12px',
                  padding: '2.5rem 1.5rem',
                  textAlign: 'center',
                  background: dragOver ? 'var(--accent-soft)' : 'var(--panel-soft)',
                  transition: 'background 160ms ease, border-color 160ms ease',
                  cursor: 'pointer',
                  marginBottom: '1.25rem',
                }}
              >
                <div style={{ marginBottom: '0.75rem', color: 'var(--muted)' }}>
                  <IconFolder size={40} />
                </div>
                <p className="fw-bold" style={{ margin: '0 0 0.25rem', color: 'var(--heading)' }}>
                  Arrastra archivos aquí o haz clic para seleccionar
                </p>
                <p className="text-sm text-muted" style={{ margin: 0 }}>
                  {uploadMode === 'pdf'
                    ? 'Formato aceptado: .pdf — Un archivo por carga'
                    : 'Formatos aceptados: .xml, .zip — Múltiples archivos permitidos'}
                </p>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept={uploadMode === 'pdf' ? '.pdf' : '.xml,.zip'}
                  multiple={uploadMode !== 'pdf'}
                  style={{ display: 'none' }}
                  onChange={(e) => handleFilesSelected(e.target.files)}
                />
              </div>

              {/* LISTA DE ARCHIVOS SELECCIONADOS */}
              {uploadMode !== 'pdf' && uploadFilesState.length > 0 && (
                <div className="meta-item" style={{ padding: '0.75rem 1rem', marginBottom: '1.25rem' }}>
                  <p className="text-xs fw-xbold text-upper text-muted" style={{ marginBottom: '0.5rem' }}>
                    {uploadFilesState.length} archivo(s) seleccionado(s)
                  </p>
                  {uploadFilesState.map((file, i) => (
                    <div
                      key={i}
                      style={{
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                        padding: '0.35rem 0',
                        borderBottom: i < uploadFilesState.length - 1 ? '1px solid var(--border)' : 'none',
                      }}
                    >
                      <span className="text-sm" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <IconFileText size={14} className="text-muted" />
                        {file.name}
                      </span>
                      <span className="text-xs text-muted">{(file.size / 1024).toFixed(1)} KB</span>
                    </div>
                  ))}
                </div>
              )}

              {uploadMode === 'pdf' && pdfFile && (
                <div className="meta-item" style={{ padding: '0.75rem 1rem', marginBottom: '1.25rem' }}>
                  <p className="text-xs fw-xbold text-upper text-muted" style={{ marginBottom: '0.5rem' }}>
                    Archivo PDF seleccionado
                  </p>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span className="text-sm" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                      <IconFileText size={14} className="text-muted" />
                      {pdfFile.name}
                    </span>
                    <span className="text-xs text-muted">{(pdfFile.size / 1024).toFixed(1)} KB</span>
                  </div>
                </div>
              )}

              {/* RESULTADO DE PREVISUALIZACIÓN */}
              {uploadMode !== 'pdf' && uploadPreview && (
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
                          <th>Mapeo contable</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(uploadPreview.files || []).map((entry, idx) => {
                          const previewItems = entry.factura_preview?.items || []
                          const itemsWithSuggestion = previewItems.filter((item) => (
                            item?.cuenta_contable_alegra
                            || item?.centro_costo_alegra
                            || item?.suggested_cuenta_contable_alegra
                            || item?.suggested_centro_costo_alegra
                          ))
                          const sampleItems = previewItems.slice(0, 3).map(buildPreviewSuggestionText)

                          return (
                            <tr key={`${entry.file_name || 'f'}-${idx}`}>
                              <td className="text-sm">{entry.entry_name || entry.file_name || '—'}</td>
                              <td className="text-sm fw-bold">{entry.factura_preview?.numero_factura || '—'}</td>
                              <td className="text-sm">{entry.factura_preview?.nombre_proveedor || '—'}</td>
                              <td><StatusBadge status={entry.status || 'pendiente'} /></td>
                              <td className="text-sm" style={{ minWidth: '320px' }}>
                                {entry.reason ? (
                                  <span className="text-muted">{entry.reason}</span>
                                ) : (
                                  <div style={{ display: 'grid', gap: '0.35rem' }}>
                                    <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                                      <span className="text-xs fw-bold text-muted">
                                        Ítems: {previewItems.length}
                                      </span>
                                      <span className="text-xs fw-bold" style={{ color: 'var(--success)' }}>
                                        Con sugerencia: {itemsWithSuggestion.length}
                                      </span>
                                    </div>

                                    {sampleItems.length > 0 ? sampleItems.map((item, i) => (
                                      <div
                                        key={`${entry.file_name || 'f'}-suggestion-${i}`}
                                        className="meta-item"
                                        style={{
                                          padding: '0.35rem 0.5rem',
                                        }}
                                      >
                                        <div className="text-xs fw-bold" style={{ color: 'var(--heading)', marginBottom: '2px' }}>
                                          {item.descripcion}
                                        </div>
                                        <div className="text-xs text-muted">
                                          Cuenta: <strong>{item.cuenta}</strong> · Centro: <strong>{item.centro}</strong>
                                        </div>
                                        <div className="text-xs text-muted">
                                          Fuente: {item.source} · Confianza: {item.confidenceText}
                                        </div>
                                      </div>
                                    )) : (
                                      <span className="text-muted text-xs">Sin información de sugerencias</span>
                                    )}

                                    {previewItems.length > 3 && (
                                      <span className="text-xs text-muted">
                                        + {previewItems.length - 3} ítem(s) adicionales en esta factura.
                                      </span>
                                    )}
                                  </div>
                                )}
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {uploadMode === 'pdf' && pdfPreview && (
                <div style={{ marginTop: '20px' }}>
                  <div className="text-sm fw-bold text-muted" style={{ marginBottom: '0.5rem' }}>
                    PDF extraído — Páginas: {pdfPreview.extraction?.pages || 0} · Revisión obligatoria
                  </div>
                  {(pdfPreview.extraction?.warnings || []).length > 0 && (
                    <div className="ui-alert" role="alert" style={{ marginBottom: '12px' }}>
                      {pdfPreview.extraction.warnings.join(' · ')}
                    </div>
                  )}
                  {pdfPreview.preview ? (
                    <div className="table-responsive" style={{ borderRadius: '0.375rem', border: '1px solid var(--border)' }}>
                      <table className="table-admin">
                        <thead>
                          <tr>
                            <th>Factura</th>
                            <th>Proveedor</th>
                            <th>Estado</th>
                            <th>Mapeo contable</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(pdfPreview.preview.facturas || []).map((entry, idx) => {
                            const previewItems = entry.factura_preview?.items || []
                            const itemsWithSuggestion = previewItems.filter((item) => (
                              item?.cuenta_contable_alegra
                              || item?.centro_costo_alegra
                              || item?.suggested_cuenta_contable_alegra
                              || item?.suggested_centro_costo_alegra
                            ))
                            const sampleItems = previewItems.slice(0, 3).map(buildPreviewSuggestionText)

                            return (
                              <tr key={`pdf-preview-${idx}`}>
                                <td className="text-sm fw-bold">{entry.factura_preview?.numero_factura || '—'}</td>
                                <td className="text-sm">{entry.factura_preview?.nombre_proveedor || '—'}</td>
                                <td><StatusBadge status={entry.status || 'pendiente'} /></td>
                                <td className="text-sm" style={{ minWidth: '320px' }}>
                                  {entry.reason ? (
                                    <span className="text-muted">{entry.reason}</span>
                                  ) : (
                                    <div style={{ display: 'grid', gap: '0.35rem' }}>
                                      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                                        <span className="text-xs fw-bold text-muted">
                                          Ítems: {previewItems.length}
                                        </span>
                                        <span className="text-xs fw-bold" style={{ color: 'var(--success)' }}>
                                          Con sugerencia: {itemsWithSuggestion.length}
                                        </span>
                                      </div>

                                      {sampleItems.length > 0 ? sampleItems.map((item, i) => (
                                        <div
                                          key={`pdf-suggestion-${i}`}
                                          className="meta-item"
                                          style={{
                                            padding: '0.35rem 0.5rem',
                                          }}
                                        >
                                          <div className="text-xs fw-bold" style={{ color: 'var(--heading)', marginBottom: '2px' }}>
                                            {item.descripcion}
                                          </div>
                                          <div className="text-xs text-muted">
                                            Cuenta: <strong>{item.cuenta}</strong> · Centro: <strong>{item.centro}</strong>
                                          </div>
                                          <div className="text-xs text-muted">
                                            Fuente: {item.source} · Confianza: {item.confidenceText}
                                          </div>
                                        </div>
                                      )) : (
                                        <span className="text-muted text-xs">Sin información de sugerencias</span>
                                      )}
                                    </div>
                                  )}
                                </td>
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="text-sm text-muted">Sin previsualización disponible.</div>
                  )}
                </div>
              )}

            </div>

            {/* FOOTER */}
            <div className="modal-footer">
              <button onClick={handleCloseModal} className="btn-secondary">
                Cancelar
              </button>
              {uploadMode !== 'pdf' ? (
                <>
                  <button
                    onClick={handlePreviewUpload}
                    disabled={uploadFilesState.length === 0 || uploadPreviewLoading || uploadSaving}
                    className="btn-secondary"
                  >
                    {uploadPreviewLoading ? 'Procesando…' : 'Previsualizar'}
                  </button>
                  <button
                    onClick={handleUploadFacturas}
                    disabled={uploadFilesState.length === 0 || uploadSaving || uploadPreviewLoading}
                    className="btn-primary"
                  >
                    {uploadSaving ? 'Cargando…' : 'Cargar facturas'}
                  </button>
                </>
              ) : (
                <>
                  <button
                    onClick={handlePreviewPdf}
                    disabled={!pdfFile || pdfPreviewLoading || pdfConfirming}
                    className="btn-secondary"
                  >
                    {pdfPreviewLoading ? 'Procesando…' : 'Previsualizar PDF'}
                  </button>
                  <button
                    onClick={handleConfirmPdf}
                    disabled={!pdfPreview || pdfConfirming || pdfPreviewLoading}
                    className="btn-primary"
                  >
                    {pdfConfirming ? 'Cargando…' : 'Confirmar PDF'}
                  </button>
                </>
              )}
            </div>

          </div>
        </div>
      )}
    </div>
  )
}
