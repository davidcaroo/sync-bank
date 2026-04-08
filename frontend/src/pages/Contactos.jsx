import React, { useEffect, useMemo, useState } from 'react'
import { Filter, Pencil, Plus, RotateCcw, Save, Search, Trash2, UserCheck, UserMinus, Users, X } from 'lucide-react'
import DataTable from '../components/DataTable'
import ConfirmDialog from '../components/ConfirmDialog'
import {
  createContacto,
  deleteContacto,
  getContactos,
  isApiConfigured,
  updateContacto,
} from '../lib/api'
import { useToast } from '../components/ToastProvider'

const emptyForm = {
  name: '',
  identification: '',
  identification_type: 'NIT',
  dv: '',
  kind_of_person: 'LEGAL_ENTITY',
  regime: 'COMMON_REGIME',
  department: '',
  city: '',
  address: '',
  country: 'Colombia',
  email: '',
  phone_primary: '',
  mobile: '',
  contact_type: ['provider'],
}

export default function Contactos() {
  const toast = useToast()
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [error, setError] = useState(null)
  const [query, setQuery] = useState('')
  const [tipo, setTipo] = useState('all')
  const [estadoFilter, setEstadoFilter] = useState('all')
  const [phoneFilter, setPhoneFilter] = useState('')
  const [showFilters, setShowFilters] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [deleteLoading, setDeleteLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [hasMore, setHasMore] = useState(false)
  const pageSize = 30

  const kpis = useMemo(() => {
    const activos = rows.filter((item) => item.status === 'active').length
    const inactivos = rows.filter((item) => item.status === 'inactive').length
    return {
      total: rows.length,
      activos,
      inactivos,
    }
  }, [rows])

  const fetchData = async (targetPage = page) => {
    if (!isApiConfigured) {
      setError('VITE_API_URL no esta configurado.')
      return
    }

    setLoading(true)
    setError(null)
    try {
      const response = await getContactos({
        tipo,
        estado: estadoFilter,
        search: query || undefined,
        page: targetPage,
        page_size: pageSize,
      })

      let data = response.data?.data || []
      if (phoneFilter.trim()) {
        const term = phoneFilter.toLowerCase().trim()
        data = data.filter(
          (item) =>
            (item.phone_primary || '').toLowerCase().includes(term) ||
            (item.mobile || '').toLowerCase().includes(term)
        )
      }

      setRows(data)
      setHasMore(Boolean(response.data?.has_more))
    } catch (err) {
      setError('No se pudo cargar el listado de contactos.')
      toast.error('No fue posible obtener contactos de Alegra.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData(page)
  }, [tipo, estadoFilter, page])

  const clearFilters = () => {
    setQuery('')
    setEstadoFilter('all')
    setPhoneFilter('')
    setShowFilters(false)
    setPage(1)
    fetchData(1)
  }

  const resetForm = () => {
    setForm({ ...emptyForm, contact_type: [tipo === 'all' ? 'provider' : tipo] })
    setEditingId(null)
  }

  const openCreateModal = () => {
    resetForm()
    setModalOpen(true)
  }

  const closeModal = () => {
    setModalOpen(false)
    resetForm()
  }

  const handleEdit = (row) => {
    setEditingId(row.id)
    setForm({
      name: row.name || '',
      identification: row.identification || '',
      identification_type: row.identification_type || 'NIT',
      dv: row.dv || '',
      kind_of_person: row.kind_of_person || 'LEGAL_ENTITY',
      regime: row.regime || 'COMMON_REGIME',
      department: row.department || '',
      city: row.city || '',
      address: row.address || '',
      country: row.country || 'Colombia',
      email: row.email || '',
      phone_primary: row.phone_primary || '',
      mobile: row.mobile || '',
      contact_type: row.type && row.type.length ? row.type : [tipo === 'all' ? 'provider' : tipo],
    })
    setModalOpen(true)
  }

  const handleSubmit = async () => {
    if (!form.name.trim()) {
      toast.warning('El nombre del contacto es obligatorio.')
      return
    }

    if (!form.identification.trim()) {
      toast.warning('El numero de identificacion es obligatorio.')
      return
    }

    setSaving(true)
    setError(null)
    try {
      if (editingId) {
        await updateContacto(editingId, form)
      } else {
        await createContacto(form)
      }
      await fetchData(page)
      closeModal()
      toast.success(editingId ? 'Contacto actualizado.' : 'Contacto creado correctamente.')
    } catch (err) {
      const msg = err?.response?.data?.detail || 'No se pudo guardar el contacto.'
      setError(msg)
      toast.error(msg)
    } finally {
      setSaving(false)
    }
  }

  const confirmDelete = async () => {
    if (!deleteTarget) return

    setDeleteLoading(true)
    setError(null)
    try {
      await deleteContacto(deleteTarget.id)
      await fetchData(page)
      toast.success('Contacto eliminado correctamente.')
      if (String(editingId) === String(deleteTarget.id)) {
        resetForm()
      }
    } catch (err) {
      const msg = err?.response?.data?.detail || 'No se pudo eliminar el contacto.'
      setError(msg)
      toast.error(msg)
    } finally {
      setDeleteLoading(false)
      setDeleteTarget(null)
    }
  }

  const toggleStatus = async (row) => {
    const nextStatus = row.status === 'active' ? 'inactive' : 'active'
    setLoading(true)
    try {
      await updateContacto(row.id, { ...row, status: nextStatus })
      await fetchData(page)
      toast.success(`Contacto ${nextStatus === 'active' ? 'activado' : 'desactivado'}.`)
    } catch (err) {
      toast.error('No se pudo cambiar el estado del contacto.')
    } finally {
      setLoading(false)
    }
  }

  const columns = [
    { key: 'name', label: 'Nombre' },
    { key: 'identification', label: 'NIT / Identificacion' },
    {
      key: 'phone_primary',
      label: 'Telefono',
      render: (row) => row.phone_primary || row.mobile || '-',
    },
    {
      key: 'type',
      label: 'Tipo',
      render: (row) => (row.type || []).join(', ') || '-',
    },
    {
      key: 'status',
      label: 'Estado',
      render: (row) => (
        <span className={row.status === 'active' ? 'badge-success' : 'badge-muted'}>
          {(row.status || 'active').toUpperCase()}
        </span>
      ),
    },
    {
      key: 'actions',
      label: 'Acciones',
      render: (row) => (
        <div className="flex gap-2">
          <button
            className="icon-btn"
            title="Editar"
            onClick={(event) => {
              event.stopPropagation()
              handleEdit(row)
            }}
          >
            <Pencil size={14} />
          </button>
          <button
            className="icon-btn"
            title={row.status === 'active' ? 'Desactivar' : 'Activar'}
            onClick={(event) => {
              event.stopPropagation()
              toggleStatus(row)
            }}
          >
            {row.status === 'active' ? <UserMinus size={14} className="text-orange-500" /> : <UserCheck size={14} className="text-green-500" />}
          </button>
          <button
            className="btn-danger p-0 w-[34px] h-[34px] flex items-center justify-center"
            title="Eliminar"
            onClick={(event) => {
              event.stopPropagation()
              setDeleteTarget(row)
            }}
          >
            <Trash2 size={14} />
          </button>
        </div>
      ),
    },
  ]

  const selectedType = (form.contact_type || []).includes('client') ? 'client' : 'provider'

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold">Contactos</h2>
          <p className="text-gray-400 mt-1">Gestion de clientes y proveedores.</p>
        </div>
        <button className="btn-primary flex items-center gap-2" onClick={openCreateModal}>
          <Plus size={16} />
          Nuevo contacto
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="panel-card px-4 py-3 flex items-center justify-between">
          <span className="text-sm text-gray-400">Registros visibles</span>
          <span className="text-lg font-bold text-[var(--heading)]">{kpis.total}</span>
        </div>
        <div className="panel-card px-4 py-3 flex items-center justify-between">
          <span className="text-sm text-gray-400">Activos</span>
          <span className="text-lg font-bold text-[var(--success)]">{kpis.activos}</span>
        </div>
        <div className="panel-card px-4 py-3 flex items-center justify-between">
          <span className="text-sm text-gray-400">Inactivos</span>
          <span className="text-lg font-bold text-[var(--warning)]">{kpis.inactivos}</span>
        </div>
      </div>

      <div className="flex gap-4 border-b border-white/5 mb-2">
        {[
          { id: 'all', label: 'Todos' },
          { id: 'client', label: 'Clientes' },
          { id: 'provider', label: 'Proveedores' },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => {
              setTipo(tab.id)
              setPage(1)
            }}
            className={`pb-3 px-2 text-sm font-semibold transition-colors relative ${
              tipo === tab.id ? 'text-[var(--heading)]' : 'text-gray-400 hover:text-[var(--heading)]'
            }`}
          >
            {tab.label}
            {tipo === tab.id && (
              <div className="absolute bottom-0 left-0 right-0 h-[3px] rounded-full bg-[var(--accent)]" />
            )}
          </button>
        ))}
      </div>

      <div className="panel-card rounded-xl p-4 space-y-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative w-full md:max-w-[420px]">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
            <input
              className="input pl-10 h-11"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  setPage(1)
                  fetchData(1)
                }
              }}
              placeholder="Buscar por nombre, NIT o email"
            />
          </div>
          <div className="min-w-[180px]">
            <select
              className="input h-11"
              value={estadoFilter}
              onChange={(event) => {
                setEstadoFilter(event.target.value)
                setPage(1)
              }}
            >
              <option value="all">Estado: Todos</option>
              <option value="active">Estado: Activos</option>
              <option value="inactive">Estado: Inactivos</option>
            </select>
          </div>
          <button
            className={`btn-secondary h-11 flex items-center gap-2 ${showFilters ? 'border-[var(--accent)]' : ''}`}
            onClick={() => setShowFilters(!showFilters)}
          >
            <Filter size={16} />
            Filtros
          </button>
          <button
            className="btn-primary h-11 px-8"
            onClick={() => {
              setPage(1)
              fetchData(1)
            }}
          >
            Buscar
          </button>
        </div>

        {showFilters && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t border-white/5 animate-in slide-in-from-top-2 duration-300">
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-400 uppercase tracking-wider font-bold">Telefono</span>
              <input
                className="input h-9 text-sm"
                placeholder="Filtrar por numero..."
                value={phoneFilter}
                onChange={(event) => setPhoneFilter(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') {
                    setPage(1)
                    fetchData(1)
                  }
                }}
              />
            </div>
            <button
              className="text-xs text-gray-500 hover:text-[var(--heading)] flex items-center gap-1.5 md:justify-end transition-colors"
              onClick={clearFilters}
            >
              <RotateCcw size={14} />
              Remover filtros
            </button>
          </div>
        )}
      </div>

      {error && <div className="ui-alert text-sm">{error}</div>}

      <DataTable
        columns={columns}
        data={rows}
        loading={loading}
        onRowClick={handleEdit}
        emptyLabel="No hay contactos para los filtros actuales."
      />

      <div className="flex items-center justify-between text-sm text-gray-400">
        <span>Pagina {page} · {rows.length} resultados</span>
        <div className="flex gap-2">
          <button
            className="btn-secondary"
            disabled={page <= 1 || loading}
            onClick={() => setPage((prev) => Math.max(1, prev - 1))}
          >
            Anterior
          </button>
          <button
            className="btn-secondary"
            disabled={!hasMore || loading}
            onClick={() => setPage((prev) => prev + 1)}
          >
            Siguiente
          </button>
        </div>
      </div>

      {modalOpen && (
        <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-4xl rounded-xl overflow-hidden border border-[var(--border)] bg-[var(--panel)] shadow-[0_24px_48px_rgba(30,40,60,.28)] animate-in fade-in zoom-in-95 duration-200">
            <div className="px-6 py-4 border-b border-[var(--border)] flex items-center justify-between">
              <div>
                <h3 className="text-xl font-bold text-[var(--heading)]">{editingId ? 'Editar contacto' : 'Nuevo contacto'}</h3>
                <p className="text-xs text-[var(--muted)] mt-0.5">Formulario principal alineado con Alegra.</p>
              </div>
              <button className="icon-btn" onClick={closeModal} aria-label="Cerrar modal">
                <X size={16} />
              </button>
            </div>

            <div className="px-6 py-5 space-y-5 max-h-[70vh] overflow-y-auto">
              <div className="grid grid-cols-2 gap-3">
                <button
                  className={selectedType === 'client' ? 'btn-primary' : 'btn-secondary'}
                  onClick={() => setForm((prev) => ({ ...prev, contact_type: ['client'] }))}
                >
                  Cliente
                </button>
                <button
                  className={selectedType === 'provider' ? 'btn-primary' : 'btn-secondary'}
                  onClick={() => setForm((prev) => ({ ...prev, contact_type: ['provider'] }))}
                >
                  Proveedor
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-12 gap-4">
                <div className="space-y-1.5 md:col-span-4">
                  <label className="text-xs text-[var(--muted)] uppercase tracking-wide font-bold">Tipo de identificacion</label>
                  <select
                    className="input"
                    value={form.identification_type}
                    onChange={(event) => setForm((prev) => ({ ...prev, identification_type: event.target.value }))}
                  >
                    <option value="NIT">NIT</option>
                    <option value="CC">Cedula</option>
                    <option value="CE">Cedula extranjera</option>
                    <option value="PP">Pasaporte</option>
                    <option value="TI">Tarjeta de identidad</option>
                  </select>
                </div>

                <div className="space-y-1.5 md:col-span-6">
                  <label className="text-xs text-[var(--muted)] uppercase tracking-wide font-bold">Numero de identificacion</label>
                  <input
                    className="input"
                    placeholder="Numero"
                    value={form.identification}
                    onChange={(event) => setForm((prev) => ({ ...prev, identification: event.target.value }))}
                  />
                </div>

                <div className="space-y-1.5 md:col-span-2">
                  <label className="text-xs text-[var(--muted)] uppercase tracking-wide font-bold">DV</label>
                  <input
                    className="input"
                    placeholder="DV"
                    value={form.dv}
                    onChange={(event) => setForm((prev) => ({ ...prev, dv: event.target.value }))}
                  />
                </div>

                <div className="space-y-1.5 md:col-span-12">
                  <label className="text-xs text-[var(--muted)] uppercase tracking-wide font-bold">Razon social o nombre completo</label>
                  <input
                    className="input"
                    placeholder="Nombre completo"
                    value={form.name}
                    onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
                  />
                </div>

                <div className="space-y-1.5 md:col-span-6">
                  <label className="text-xs text-[var(--muted)] uppercase tracking-wide font-bold">Tipo de persona</label>
                  <select
                    className="input"
                    value={form.kind_of_person}
                    onChange={(event) => setForm((prev) => ({ ...prev, kind_of_person: event.target.value }))}
                  >
                    <option value="LEGAL_ENTITY">Persona juridica</option>
                    <option value="PERSON_ENTITY">Persona natural</option>
                  </select>
                </div>

                <div className="space-y-1.5 md:col-span-6">
                  <label className="text-xs text-[var(--muted)] uppercase tracking-wide font-bold">Responsabilidad tributaria</label>
                  <select
                    className="input"
                    value={form.regime}
                    onChange={(event) => setForm((prev) => ({ ...prev, regime: event.target.value }))}
                  >
                    <option value="COMMON_REGIME">Responsable de IVA</option>
                    <option value="SIMPLIFIED_REGIME">No responsable de IVA</option>
                  </select>
                </div>

                <div className="space-y-1.5 md:col-span-6">
                  <label className="text-xs text-[var(--muted)] uppercase tracking-wide font-bold">Municipio / Ciudad</label>
                  <input
                    className="input"
                    placeholder="Ciudad"
                    value={form.city}
                    onChange={(event) => setForm((prev) => ({ ...prev, city: event.target.value }))}
                  />
                </div>

                <div className="space-y-1.5 md:col-span-6">
                  <label className="text-xs text-[var(--muted)] uppercase tracking-wide font-bold">Departamento</label>
                  <input
                    className="input"
                    placeholder="Departamento"
                    value={form.department}
                    onChange={(event) => setForm((prev) => ({ ...prev, department: event.target.value }))}
                  />
                </div>

                <div className="space-y-1.5 md:col-span-8">
                  <label className="text-xs text-[var(--muted)] uppercase tracking-wide font-bold">Direccion</label>
                  <input
                    className="input"
                    placeholder="Direccion"
                    value={form.address}
                    onChange={(event) => setForm((prev) => ({ ...prev, address: event.target.value }))}
                  />
                </div>

                <div className="space-y-1.5 md:col-span-4">
                  <label className="text-xs text-[var(--muted)] uppercase tracking-wide font-bold">Pais</label>
                  <input
                    className="input"
                    placeholder="Pais"
                    value={form.country}
                    onChange={(event) => setForm((prev) => ({ ...prev, country: event.target.value }))}
                  />
                </div>

                <div className="space-y-1.5 md:col-span-6">
                  <label className="text-xs text-[var(--muted)] uppercase tracking-wide font-bold">Correo electronico</label>
                  <input
                    className="input"
                    placeholder="ejemplo@email.com"
                    value={form.email}
                    onChange={(event) => setForm((prev) => ({ ...prev, email: event.target.value }))}
                  />
                </div>

                <div className="space-y-1.5 md:col-span-3">
                  <label className="text-xs text-[var(--muted)] uppercase tracking-wide font-bold">Telefono</label>
                  <input
                    className="input"
                    placeholder="Telefono"
                    value={form.phone_primary}
                    onChange={(event) => setForm((prev) => ({ ...prev, phone_primary: event.target.value }))}
                  />
                </div>

                <div className="space-y-1.5 md:col-span-3">
                  <label className="text-xs text-[var(--muted)] uppercase tracking-wide font-bold">Celular</label>
                  <input
                    className="input"
                    placeholder="Celular"
                    value={form.mobile}
                    onChange={(event) => setForm((prev) => ({ ...prev, mobile: event.target.value }))}
                  />
                </div>
              </div>
            </div>

            <div className="px-6 py-4 border-t border-[var(--border)] bg-[var(--panel-soft)]/30 flex flex-wrap items-center justify-end gap-2">
              <button className="btn-secondary" onClick={closeModal} disabled={saving}>
                Cancelar
              </button>
              <button className="btn-primary" onClick={handleSubmit} disabled={saving}>
                <Save size={14} className="inline mr-2" />
                {saving ? 'Guardando...' : editingId ? 'Guardar cambios' : 'Crear contacto'}
              </button>
            </div>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="Confirmar eliminacion"
        message={
          deleteTarget
            ? `Vas a eliminar el contacto ${deleteTarget.name} (${deleteTarget.identification || 'sin identificacion'}).`
            : ''
        }
        confirmLabel="Eliminar"
        cancelLabel="Cancelar"
        onConfirm={confirmDelete}
        onCancel={() => setDeleteTarget(null)}
        loading={deleteLoading}
      />
    </div>
  )
}
