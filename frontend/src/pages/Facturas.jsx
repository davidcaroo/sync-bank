import React, { useEffect, useMemo, useState } from 'react'
import { Search, Filter } from 'lucide-react'
import DataTable from '../components/DataTable'
import FacturaModal from '../components/FacturaModal'
import { StatusBadge } from '../components/DashboardBase'
import { causarFactura, getAlegraCatalogo, getFacturas, isApiConfigured } from '../lib/api'
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

  const totalPages = useMemo(() => Math.max(1, Math.ceil(count / pageSize)), [count, pageSize])

  const fetchData = async () => {
    if (!isApiConfigured) {
      setError('VITE_API_URL no esta configurado.')
      return
    }

    setLoading(true)
    setError(null)
    try {
      const response = await getFacturas({
        page,
        page_size: pageSize,
        estado: filters.estado || undefined,
        proveedor: filters.proveedor || undefined,
        desde: filters.desde || undefined,
        hasta: filters.hasta || undefined,
      })

      setData(response.data.data || [])
      setCount(response.data.count || 0)
    } catch (err) {
      setError('No se pudo cargar la lista de facturas.')
      toast.error('No se pudo consultar facturas en este momento.')
    } finally {
      setLoading(false)
    }
  }

  const fetchCatalogo = async () => {
    if (!isApiConfigured) {
      return
    }

    try {
      const response = await getAlegraCatalogo()
      setCatalogo({
        categories: response.data?.categories || [],
        cost_centers: response.data?.cost_centers || [],
      })
    } catch (err) {
      setError('No se pudo cargar el catalogo de Alegra para editar items.')
      toast.warning('No se pudo cargar el catalogo de cuentas y centros.')
    }
  }

  const handleItemChange = (itemId, field, value) => {
    setSelected((prev) => {
      if (!prev) return prev

      const currentItems = prev.items_factura || []
      const updatedItems = currentItems.map((item) => (
        String(item.id) === String(itemId)
          ? { ...item, [field]: value || null }
          : item
      ))

      return { ...prev, items_factura: updatedItems }
    })
  }

  const handleCausar = async () => {
    if (!selected) return
    setCausarLoading(true)
    try {
      const itemOverrides = (selected.items_factura || []).map((item) => ({
        item_id: item.id,
        cuenta_contable_alegra: item.cuenta_contable_alegra || null,
        centro_costo_alegra: item.centro_costo_alegra || null,
      }))

      await causarFactura(selected.id, { item_overrides: itemOverrides })
      await fetchData()
      setSelected(null)
      toast.success('Factura causada correctamente en Alegra.')
    } catch (err) {
      setError('No se pudo enviar a Alegra. Revisa la configuracion.')
      toast.error('Fallo la causacion. Valida cuentas y centros por item.')
    } finally {
      setCausarLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    fetchCatalogo()
  }, [page, filters])

  const columns = [
    {
      key: 'numero_factura',
      label: 'Factura',
      render: (row) => <span className="text-blue-400 font-medium">{row.numero_factura}</span>,
    },
    { key: 'nombre_proveedor', label: 'Proveedor' },
    {
      key: 'total',
      label: 'Total',
      render: (row) => `$${Number(row.total || 0).toLocaleString()}`,
    },
    {
      key: 'estado',
      label: 'Estado',
      render: (row) => <StatusBadge status={row.estado} />,
    },
    {
      key: 'created_at',
      label: 'Fecha',
      render: (row) => new Date(row.created_at).toLocaleDateString(),
    },
  ]

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-3xl font-bold">Facturas</h2>
          <p className="text-gray-400 mt-1">Consulta completa y causacion manual.</p>
        </div>
        <div className="glass px-4 py-2 rounded-xl text-sm text-gray-400">
          Total: <span className="font-semibold text-[var(--heading)]">{count}</span>
        </div>
      </div>

      <div className="glass rounded-2xl p-5 space-y-4">
        <div className="flex items-center gap-3 text-sm text-gray-400">
          <Filter size={16} />
          <span>Filtros</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="text-xs text-gray-400">Estado</label>
            <select
              className="input"
              value={filters.estado}
              onChange={(event) => setFilters((prev) => ({ ...prev, estado: event.target.value }))}
            >
              <option value="">Todos</option>
              <option value="pendiente">Pendiente</option>
              <option value="procesado">Procesado</option>
              <option value="error">Error</option>
              <option value="duplicado">Duplicado</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-400">Proveedor</label>
            <div className="relative">
              <Search size={14} className="absolute left-3 top-3 text-gray-500" />
              <input
                className="input pl-9"
                placeholder="Buscar..."
                value={filters.proveedor}
                onChange={(event) => setFilters((prev) => ({ ...prev, proveedor: event.target.value }))}
              />
            </div>
          </div>
          <div>
            <label className="text-xs text-gray-400">Desde</label>
            <input
              type="date"
              className="input"
              value={filters.desde}
              onChange={(event) => setFilters((prev) => ({ ...prev, desde: event.target.value }))}
            />
          </div>
          <div>
            <label className="text-xs text-gray-400">Hasta</label>
            <input
              type="date"
              className="input"
              value={filters.hasta}
              onChange={(event) => setFilters((prev) => ({ ...prev, hasta: event.target.value }))}
            />
          </div>
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
        onRowClick={(row) => setSelected(row)}
        emptyLabel="No hay facturas para los filtros actuales."
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
