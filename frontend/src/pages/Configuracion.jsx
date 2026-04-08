import React, { useEffect, useState } from 'react'
import { Building2, Landmark, Plus, Save, Trash2 } from 'lucide-react'
import DataTable from '../components/DataTable'
import {
  createConfigCuenta,
  deleteConfigCuenta,
  getAlegraCatalogo,
  getConfigCuentas,
  isApiConfigured,
  updateConfigCuenta,
} from '../lib/api'
import { useToast } from '../components/ToastProvider'

const emptyForm = {
  nit_proveedor: '',
  nombre_cuenta: '',
  id_cuenta_alegra: '',
  id_retefuente: '',
  id_reteica: '',
  id_reteiva: '',
  activo: true,
}

export default function Configuracion() {
  const toast = useToast()
  const [data, setData] = useState([])
  const [catalogo, setCatalogo] = useState({ categories: [], cost_centers: [] })
  const [form, setForm] = useState(emptyForm)
  const [editingId, setEditingId] = useState(null)
  const [loading, setLoading] = useState(false)
  const [catalogLoading, setCatalogLoading] = useState(false)
  const [error, setError] = useState(null)

  const fetchData = async () => {
    if (!isApiConfigured) {
      setError('VITE_API_URL no esta configurado.')
      return
    }

    setLoading(true)
    setError(null)
    try {
      const response = await getConfigCuentas()
      setData(response.data || [])
    } catch (err) {
      setError('No se pudo cargar configuracion de cuentas.')
      toast.error('No fue posible cargar la configuracion guardada.')
    } finally {
      setLoading(false)
    }
  }

  const fetchCatalogo = async (refresh = false) => {
    if (!isApiConfigured) {
      return
    }

    setCatalogLoading(true)
    try {
      const response = await getAlegraCatalogo(refresh ? { refresh: true } : undefined)
      setCatalogo({
        categories: response.data?.categories || [],
        cost_centers: response.data?.cost_centers || [],
      })
    } catch (err) {
      setError('No se pudo cargar el catalogo de Alegra.')
      toast.warning('No se pudo obtener el catalogo desde Alegra.')
    } finally {
      setCatalogLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    fetchCatalogo()
  }, [])

  const handleCuentaChange = (value) => {
    const match = catalogo.categories.find((item) => String(item.id) === String(value))
    setForm((prev) => ({
      ...prev,
      id_cuenta_alegra: value,
      nombre_cuenta: match?.name || prev.nombre_cuenta,
    }))
  }

  const resetForm = () => {
    setForm(emptyForm)
    setEditingId(null)
  }

  const handleSubmit = async () => {
    setLoading(true)
    setError(null)
    try {
      const payload = {
        ...form,
        id_retefuente: form.id_retefuente || null,
        id_reteica: form.id_reteica || null,
        id_reteiva: form.id_reteiva || null,
      }

      if (editingId) {
        await updateConfigCuenta(editingId, payload)
      } else {
        await createConfigCuenta(payload)
      }

      resetForm()
      await fetchData()
      toast.success(editingId ? 'Configuracion actualizada.' : 'Configuracion creada correctamente.')
    } catch (err) {
      setError('No se pudo guardar el registro.')
      toast.error('No se pudo guardar el mapeo de cuenta.')
    } finally {
      setLoading(false)
    }
  }

  const handleEdit = (row) => {
    setEditingId(row.id)
    setForm({
      nit_proveedor: row.nit_proveedor || '',
      nombre_cuenta: row.nombre_cuenta || '',
      id_cuenta_alegra: row.id_cuenta_alegra || '',
      id_retefuente: row.id_retefuente || '',
      id_reteica: row.id_reteica || '',
      id_reteiva: row.id_reteiva || '',
      activo: row.activo ?? true,
    })
  }

  const handleToggle = async (row) => {
    try {
      await updateConfigCuenta(row.id, { activo: !row.activo })
      await fetchData()
    } catch (err) {
      setError('No se pudo actualizar el estado.')
      toast.error('No se pudo cambiar el estado del registro.')
    }
  }

  const handleDelete = async (row) => {
    try {
      await deleteConfigCuenta(row.id)
      await fetchData()
    } catch (err) {
      setError('No se pudo eliminar el registro.')
      toast.error('No se pudo eliminar el registro seleccionado.')
    }
  }

  const columns = [
    { key: 'nit_proveedor', label: 'NIT Proveedor' },
    { key: 'nombre_cuenta', label: 'Cuenta' },
    { key: 'id_cuenta_alegra', label: 'ID Alegra' },
    {
      key: 'activo',
      label: 'Activo',
      render: (row) => (
        <button
          className={row.activo ? 'badge-success' : 'badge-muted'}
          onClick={(event) => {
            event.stopPropagation()
            handleToggle(row)
          }}
        >
          {row.activo ? 'Activo' : 'Inactivo'}
        </button>
      ),
    },
    {
      key: 'actions',
      label: 'Acciones',
      render: (row) => (
        <div className="flex gap-2">
          <button
            className="btn-secondary"
            onClick={(event) => {
              event.stopPropagation()
              handleEdit(row)
            }}
          >
            Editar
          </button>
          <button
            className="btn-danger"
            onClick={(event) => {
              event.stopPropagation()
              handleDelete(row)
            }}
          >
            <Trash2 size={14} />
          </button>
        </div>
      ),
    },
  ]

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div>
        <h2 className="text-3xl font-bold">Cuentas</h2>
        <p className="text-gray-400 mt-1">Mapeo NIT a cuentas contables en Alegra.</p>
      </div>

      <div className="panel-card p-6 space-y-4">
        <div className="flex items-center gap-2 text-sm text-gray-400">
          <Plus size={16} />
          <span>{editingId ? 'Editar registro' : 'Nuevo registro'}</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <input
            className="input"
            placeholder="NIT proveedor"
            value={form.nit_proveedor}
            onChange={(event) => setForm((prev) => ({ ...prev, nit_proveedor: event.target.value }))}
          />
          <input
            className="input"
            placeholder="Nombre cuenta"
            value={form.nombre_cuenta}
            onChange={(event) => setForm((prev) => ({ ...prev, nombre_cuenta: event.target.value }))}
          />
          <select
            className="input"
            value={form.id_cuenta_alegra}
            onChange={(event) => handleCuentaChange(event.target.value)}
          >
            <option value="">Selecciona cuenta Alegra</option>
            {catalogo.categories.map((item) => (
              <option key={item.id} value={item.id}>
                {(item.code || item.id)} | {item.name}
              </option>
            ))}
          </select>
          <input
            className="input"
            placeholder="ID retefuente"
            value={form.id_retefuente}
            onChange={(event) => setForm((prev) => ({ ...prev, id_retefuente: event.target.value }))}
          />
          <input
            className="input"
            placeholder="ID reteica"
            value={form.id_reteica}
            onChange={(event) => setForm((prev) => ({ ...prev, id_reteica: event.target.value }))}
          />
          <input
            className="input"
            placeholder="ID reteiva"
            value={form.id_reteiva}
            onChange={(event) => setForm((prev) => ({ ...prev, id_reteiva: event.target.value }))}
          />
        </div>
        <div className="flex items-center justify-between">
          <label className="flex items-center gap-2 text-sm text-gray-400">
            <input
              type="checkbox"
              checked={form.activo}
              onChange={(event) => setForm((prev) => ({ ...prev, activo: event.target.checked }))}
            />
            Activo
          </label>
          <div className="flex gap-2">
            <button className="btn-secondary" onClick={() => fetchCatalogo(true)} disabled={catalogLoading}>
              {catalogLoading ? 'Actualizando catalogo...' : 'Actualizar catalogo Alegra'}
            </button>
            <button className="btn-secondary" onClick={resetForm} disabled={loading}>
              Cancelar
            </button>
            <button className="btn-primary" onClick={handleSubmit} disabled={loading}>
              <Save size={14} className="inline mr-2" />
              Guardar
            </button>
          </div>
        </div>
      </div>

      <div className="panel-card p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold">Catalogo real de Alegra</h3>
          <span className="text-xs text-gray-400">
            {catalogo.categories.length} cuentas | {catalogo.cost_centers.length} centros de costo
          </span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="panel-card">
            <div className="panel-header">
              <div className="flex items-center gap-2">
                <Landmark size={16} />
                <h3>Cuentas contables</h3>
              </div>
              <p>{catalogo.categories.length} registros</p>
            </div>
            <div className="overflow-auto max-h-72">
              <table className="table-admin min-w-full">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Codigo</th>
                    <th>Nombre</th>
                  </tr>
                </thead>
                <tbody>
                  {catalogo.categories.map((item) => (
                    <tr key={item.id}>
                      <td>{item.id}</td>
                      <td>{item.code || '-'}</td>
                      <td>{item.name}</td>
                    </tr>
                  ))}
                  {catalogo.categories.length === 0 && (
                    <tr>
                      <td colSpan={3}>Sin cuentas cargadas.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
          <div className="panel-card">
            <div className="panel-header">
              <div className="flex items-center gap-2">
                <Building2 size={16} />
                <h3>Centros de costo</h3>
              </div>
              <p>{catalogo.cost_centers.length} registros</p>
            </div>
            <div className="overflow-auto max-h-72">
              <table className="table-admin min-w-full">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Nombre</th>
                    <th>Estado</th>
                  </tr>
                </thead>
                <tbody>
                  {catalogo.cost_centers.map((item) => (
                    <tr key={item.id}>
                      <td>{item.id}</td>
                      <td>{item.name}</td>
                      <td>{item.status || 'active'}</td>
                    </tr>
                  ))}
                  {catalogo.cost_centers.length === 0 && (
                    <tr>
                      <td colSpan={3}>Sin centros de costo cargados.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
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
        emptyLabel="No hay cuentas configuradas."
      />
    </div>
  )
}
