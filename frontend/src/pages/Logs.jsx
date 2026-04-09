import React, { useEffect, useMemo, useState } from 'react'
import { Mail, SlidersHorizontal, X, History } from 'lucide-react'
import { getLogs, isApiConfigured } from '../lib/api'
import { useToast } from '../components/ToastProvider'

const DEFAULT_PAGE_SIZE = 10

const logBadgeClass = {
  procesado: 'badge-success',
  ignorado:  'badge-muted',
  error:     'badge-danger',
}

export default function Logs() {
  const toast = useToast()
  const [page,    setPage]    = useState(1)
  const [pageSize]            = useState(DEFAULT_PAGE_SIZE)
  const [data,    setData]    = useState([])
  const [count,   setCount]   = useState(0)
  const [estado,  setEstado]  = useState('')
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState(null)

  const totalPages = useMemo(() => Math.max(1, Math.ceil(count / pageSize)), [count, pageSize])

  const fetchData = async () => {
    if (!isApiConfigured) { setError('VITE_API_URL no está configurado.'); return }
    setLoading(true); setError(null)
    try {
      const response = await getLogs({ page, page_size: pageSize, estado: estado || undefined })
      setData(response.data.data  || [])
      setCount(response.data.count || 0)
    } catch {
      setError('No se pudieron cargar los logs.')
      toast.error('No se pudo recuperar la auditoría de emails.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [page, estado])
  useEffect(() => { setPage(1)  }, [estado])

  return (
    <div>
      {/* ── Page heading ──────────────────────────────────────── */}
      <div className="page-heading">
        <div>
          <h1 className="page-heading-title">Centro de Auditoría</h1>
          <p className="page-heading-sub">Registro completo de emails procesados</p>
        </div>
        <div className="audit-count-chip">
          <Mail size={15} />
          <span><strong>{count}</strong> registro{count !== 1 ? 's' : ''}</span>
        </div>
      </div>

      {error && <div className="ui-alert" role="alert">{error}</div>}

      {/* ── Filtros ───────────────────────────────────────────── */}
      <div className="audit-toolbar">
        <div className="audit-toolbar-title">
          <SlidersHorizontal size={15} />
          <span>Filtrar por estado</span>
        </div>
        <div className="audit-toolbar-controls">
          <label className="sr-only" htmlFor="estado-log">Estado del proceso</label>
          <select
            id="estado-log"
            className="input audit-select"
            value={estado}
            onChange={(e) => setEstado(e.target.value)}
          >
            <option value="">Todos los estados</option>
            <option value="procesado">Procesado</option>
            <option value="ignorado">Ignorado</option>
            <option value="error">Error</option>
          </select>
          <button
            type="button"
            className="btn-secondary audit-clear-btn"
            onClick={() => setEstado('')}
            disabled={!estado}
          >
            <X size={13} />
            Limpiar
          </button>
        </div>
      </div>

      {/* ── Logs table card ───────────────────────────────────── */}
      <div className="sb-card">
        <div className="sb-card-header">
          <h2 className="sb-card-header-title" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <History size={14} /> Registros de auditoría
          </h2>
        </div>

        <div className="table-responsive">
          <table className="table-admin" aria-label="Auditoría de emails">
            <thead>
              <tr>
                <th style={{ width: '40%' }}>Asunto / Remitente</th>
                <th>Adjuntos</th>
                <th>Estado</th>
                <th className="d-none-mobile">Fecha</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td colSpan={4}>
                    <div className="table-empty">
                      <div className="table-empty-icon">⏳</div>
                      <p className="fw-bold">Cargando registros…</p>
                    </div>
                  </td>
                </tr>
              )}

              {!loading && data.map((row) => (
                <tr key={row.id}>
                  <td>
                    <p className="fw-bold text-sm" style={{ color: 'var(--heading)', marginBottom: '0.1rem' }}>
                      {row.asunto || '(Sin asunto)'}
                    </p>
                    <p className="text-xs text-muted">{row.remitente}</p>
                  </td>
                  <td>
                    <span
                      className="status-badge badge-info"
                      style={{ fontSize: '0.75rem' }}
                    >
                      {row.attachments_encontrados ?? 0}
                    </span>
                  </td>
                  <td>
                    <span className={`status-badge ${logBadgeClass[row.estado] || 'badge-muted'}`}>
                      {row.estado}
                    </span>
                  </td>
                  <td className="d-none-mobile text-sm text-muted">
                    {new Date(row.created_at).toLocaleString('es-CO', {
                      day: '2-digit', month: 'short', year: 'numeric',
                      hour: '2-digit', minute: '2-digit',
                    })}
                  </td>
                </tr>
              ))}

              {!loading && data.length === 0 && (
                <tr>
                  <td colSpan={4}>
                    <div className="table-empty">
                      <div className="table-empty-icon">📭</div>
                      <p className="fw-bold">No hay registros para el filtro actual</p>
                      <p className="text-sm text-muted mt-1">
                        {estado ? `No hay emails con estado "${estado}".` : 'Aún no se han procesado emails.'}
                      </p>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination inside card footer */}
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
    </div>
  )
}
