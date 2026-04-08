import React, { useEffect, useMemo, useState } from 'react'
import { Mail, SlidersHorizontal, X } from 'lucide-react'
import DataTable from '../components/DataTable'
import { getLogs, isApiConfigured } from '../lib/api'
import { useToast } from '../components/ToastProvider'

const DEFAULT_PAGE_SIZE = 10

export default function Logs() {
  const toast = useToast()
  const [page, setPage] = useState(1)
  const [pageSize] = useState(DEFAULT_PAGE_SIZE)
  const [data, setData] = useState([])
  const [count, setCount] = useState(0)
  const [estado, setEstado] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const totalPages = useMemo(() => Math.max(1, Math.ceil(count / pageSize)), [count, pageSize])

  const fetchData = async () => {
    if (!isApiConfigured) {
      setError('VITE_API_URL no esta configurado.')
      return
    }

    setLoading(true)
    setError(null)
    try {
      const response = await getLogs({ page, page_size: pageSize, estado: estado || undefined })
      setData(response.data.data || [])
      setCount(response.data.count || 0)
    } catch (err) {
      setError('No se pudieron cargar los logs.')
      toast.error('No se pudo recuperar la auditoria de emails.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [page, estado])

  useEffect(() => {
    setPage(1)
  }, [estado])

  const columns = [
    {
      key: 'asunto',
      label: 'Asunto',
      render: (row) => (
        <div>
          <p className="font-medium">{row.asunto || '(Sin asunto)'}</p>
          <p className="text-xs text-gray-400">{row.remitente}</p>
        </div>
      ),
    },
    {
      key: 'attachments_encontrados',
      label: 'Adjuntos',
      render: (row) => row.attachments_encontrados ?? 0,
    },
    {
      key: 'estado',
      label: 'Estado',
      render: (row) => {
        const badgeClass = row.estado === 'procesado'
          ? 'badge-success'
          : row.estado === 'error'
            ? 'badge-danger'
            : 'badge-muted'
        return <span className={badgeClass}>{row.estado}</span>
      },
    },
    {
      key: 'created_at',
      label: 'Fecha',
      render: (row) => new Date(row.created_at).toLocaleString(),
    },
  ]

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="space-y-1">
          <h2 className="text-3xl font-bold leading-tight">Auditoria</h2>
          <p className="text-gray-400">Registro de emails procesados.</p>
        </div>
        <div className="audit-count-chip">
          <Mail size={16} />
          <span>{count} registros</span>
        </div>
      </div>

      <div className="audit-toolbar">
        <div className="audit-toolbar-title">
          <SlidersHorizontal size={16} />
          <span>Filtros</span>
        </div>
        <div className="audit-toolbar-controls">
          <label className="sr-only" htmlFor="estado-log">Estado del proceso</label>
          <select
            id="estado-log"
            className="input audit-select"
            value={estado}
            onChange={(event) => setEstado(event.target.value)}
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
            <X size={14} />
            Limpiar
          </button>
        </div>
      </div>

      {error && (
        <div className="ui-alert text-sm">
          {error}
        </div>
      )}

      <DataTable
        columns={columns}
        data={data}
        loading={loading}
        emptyLabel="No hay logs para el filtro actual."
      />

      <div className="flex items-center justify-between text-sm text-gray-400">
        <span>
          Pagina {page} de {totalPages}
        </span>
        <div className="flex gap-2">
          <button
            className="btn-secondary"
            disabled={page === 1}
            onClick={() => setPage((prev) => Math.max(1, prev - 1))}
          >
            Anterior
          </button>
          <button
            className="btn-secondary"
            disabled={page >= totalPages}
            onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))}
          >
            Siguiente
          </button>
        </div>
      </div>
    </div>
  )
}
