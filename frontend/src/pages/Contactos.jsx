import React, { useEffect, useMemo, useState } from 'react'
import { Filter, Pencil, Plus, RotateCcw, Save, Search, Trash2, UserCheck, UserMinus, Users, X } from 'lucide-react'
import ConfirmDialog from '../components/ConfirmDialog'
import { StatusBadge, KpiCard } from '../components/DashboardBase'
import {
  createContacto,
  deleteContacto,
  getContactos,
  isApiConfigured,
  updateContacto,
} from '../lib/api'
import { useToast } from '../components/ToastProvider'

const identificationTypeOptions = [
  { value: 'NIT', label: 'NIT - Número de identificación tributaria' },
  { value: 'CC', label: 'CC - Cédula de ciudadanía' },
  { value: 'NIT de otro pais', label: 'NIT de otro país' },
  { value: 'PP', label: 'PP - Pasaporte' },
  { value: 'PEP', label: 'PEP - Permiso especial de permanencia' },
  { value: 'DIE', label: 'DIE - Documento de identificación extranjero' },
  { value: 'CE', label: 'CE - Cédula de extranjería' },
  { value: 'TE', label: 'TE - Tarjeta de extranjería' },
  { value: 'TI', label: 'TI - Tarjeta de identidad' },
  { value: 'RC', label: 'RC - Registro civil' },
  { value: 'NUIP', label: 'NUIP - Número único de identificación personal' },
]

const regimeOptions = [
  { value: 'Responsable de IVA', label: 'Responsable de IVA' },
  { value: 'No responsable de IVA', label: 'No responsable de IVA' },
  { value: 'Impuesto Nacional al Consumo - INC', label: 'Impuesto Nacional al Consumo - INC' },
  { value: 'No responsable de INC', label: 'No responsable de INC' },
  { value: 'Responsable de IVA e INC', label: 'Responsable de IVA e INC' },
  { value: 'Regimen especial', label: 'Regimen especial' },
]

const normalizeRegimeForForm = (value) => {
  if (value === 'COMMON_REGIME') return 'Responsable de IVA'
  if (value === 'SIMPLIFIED_REGIME') return 'No responsable de IVA'
  return value || 'Responsable de IVA'
}

const normalizeRegimeForApi = (value) => {
  if (value === 'Responsable de IVA') return 'COMMON_REGIME'
  if (value === 'No responsable de IVA') return 'SIMPLIFIED_REGIME'
  return value
}

const emptyForm = {
  name: '',
  identification: '',
  identification_type: 'NIT',
  dv: '',
  kind_of_person: 'LEGAL_ENTITY',
  regime: 'Responsable de IVA',
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
    const total = rows.length
    const activos = rows.filter((item) => item.status === 'active').length
    const inactivos = rows.filter((item) => item.status === 'inactive').length
    return { total, activos, inactivos }
  }, [rows])

  const fetchData = async (targetPage = page) => {
    if (!isApiConfigured) {
      setError('VITE_API_URL no está configurado.')
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
      regime: normalizeRegimeForForm(row.regime),
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
      toast.warning('El número de identificación es obligatorio.')
      return
    }

    setSaving(true)
    setError(null)
    try {
      const payload = {
        ...form,
        regime: normalizeRegimeForApi(form.regime),
      }

      if (editingId) {
        await updateContacto(editingId, payload)
      } else {
        await createContacto(payload)
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

  const selectedType = (form.contact_type || []).includes('client') ? 'client' : 'provider'

  return (
    <div>
      {/* ── Page heading ──────────────────────────────────────────── */}
      <div className="page-heading">
        <div>
          <h1 className="page-heading-title">Directorio de Contactos</h1>
          <p className="page-heading-sub">Gestión centralizada de clientes y proveedores</p>
        </div>
        <button className="btn-primary" onClick={openCreateModal}>
          <Plus size={16} />
          Nuevo contacto
        </button>
      </div>

      {error && <div className="ui-alert" role="alert">{error}</div>}

      {/* ── KPI Cards ─────────────────────────────────────────────── */}
      <div className="kpi-grid">
        <KpiCard
          label="Total Visibles"
          value={kpis.total}
          icon={Users}
          color="primary"
        />
        <KpiCard
          label="Contactos Activos"
          value={kpis.activos}
          icon={UserCheck}
          color="success"
        />
        <KpiCard
          label="Contactos Inactivos"
          value={kpis.inactivos}
          icon={UserMinus}
          color="warning"
        />
      </div>

      {/* ── Tabs ── */}
      <div style={{ display: 'flex', gap: '1rem', borderBottom: '1px solid var(--border)', marginBottom: '1.5rem', overflowX: 'auto' }}>
        {[
          { id: 'all', label: 'Todos' },
          { id: 'client', label: 'Clientes' },
          { id: 'provider', label: 'Proveedores' },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => { setTipo(tab.id); setPage(1); }}
            style={{
              padding: '0.75rem 1rem',
              fontSize: '0.875rem',
              fontWeight: 700,
              color: tipo === tab.id ? 'var(--accent)' : 'var(--muted)',
              borderBottom: tipo === tab.id ? '2px solid var(--accent)' : '2px solid transparent',
              background: 'none',
              cursor: 'pointer',
              transition: 'all 0.2s',
              whiteSpace: 'nowrap'
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── Filters Card ──────────────────────────────────────────── */}
      <div className="sb-card">
        <div className="sb-card-header">
           <h2 className="sb-card-header-title" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <Search size={14} /> Filtros de búsqueda
          </h2>
        </div>
        <div className="sb-card-body">
          <div className="filter-row">
            <div style={{ flex: 2 }}>
              <label>Búsqueda rápida</label>
              <div style={{ position: 'relative' }}>
                <Search size={14} style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--muted)' }} />
                <input
                  className="input"
                  style={{ paddingLeft: '2.25rem' }}
                  placeholder="Nombre, NIT o correo..."
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && (setPage(1), fetchData(1))}
                />
              </div>
            </div>
            <div>
              <label>Estado</label>
              <select className="input" value={estadoFilter} onChange={(e) => { setEstadoFilter(e.target.value); setPage(1); }}>
                <option value="all">Todos</option>
                <option value="active">Activos</option>
                <option value="inactive">Inactivos</option>
              </select>
            </div>
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: '0.5rem' }}>
               <button className="btn-primary" onClick={() => { setPage(1); fetchData(1); }}>Buscar</button>
               <button className="btn-secondary" onClick={() => setShowFilters(!showFilters)}>
                 <Filter size={14} />
               </button>
            </div>
          </div>

          {showFilters && (
            <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid var(--border)', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', alignItems: 'end' }}>
               <div>
                  <label>Teléfono</label>
                  <input className="input" placeholder="Filtrar por número..." value={phoneFilter} onChange={(e) => setPhoneFilter(e.target.value)} />
               </div>
               <div style={{ textAlign: 'right' }}>
                  <button className="btn-secondary btn-sm" onClick={clearFilters}>
                    <RotateCcw size={12} /> Limpiar filtros
                  </button>
               </div>
            </div>
          )}
        </div>
      </div>

      {/* ── Data Table ────────────────────────────────────────────── */}
      <div className="sb-card">
        <div className="sb-card-header">
           <h2 className="sb-card-header-title">Listado de Contactos</h2>
        </div>
        <div className="table-responsive">
          <table className="table-admin">
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Identificación</th>
                <th className="d-none-mobile">Teléfono</th>
                <th className="d-none-mobile">Tipo</th>
                <th>Estado</th>
                <th style={{ width: '120px', textAlign: 'center' }}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td colSpan={6}><div className="table-empty">Cargando contactos...</div></td>
                </tr>
              )}
              {!loading && rows.map((row) => (
                <tr key={row.id}>
                  <td>
                    <div className="fw-bold">{row.name}</div>
                    <div className="text-xs text-muted d-block d-md-none">{row.identification}</div>
                  </td>
                  <td>{row.identification}</td>
                  <td className="d-none-mobile">{row.phone_primary || row.mobile || '—'}</td>
                  <td className="d-none-mobile">
                    {(row.type || []).map(t => (
                      <span key={t} className="status-badge badge-info" style={{ marginRight: '0.2rem', textTransform: 'capitalize' }}>{t}</span>
                    ))}
                  </td>
                  <td>
                    <StatusBadge status={row.status === 'active' ? 'procesado' : 'error'} label={row.status} />
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: '0.35rem', justifyContent: 'center' }}>
                      <button className="btn-secondary btn-sm p-1" title="Editar" onClick={() => handleEdit(row)}>
                        <Pencil size={12} />
                      </button>
                      <button className="btn-secondary btn-sm p-1" title={row.status === 'active' ? 'Desactivar' : 'Activar'} onClick={() => toggleStatus(row)}>
                        {row.status === 'active' ? <UserMinus size={12} className="text-warning" /> : <UserCheck size={12} className="text-success" />}
                      </button>
                      <button className="btn-danger btn-sm p-1" title="Eliminar" onClick={() => setDeleteTarget(row)}>
                        <Trash2 size={12} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {!loading && rows.length === 0 && (
                <tr>
                  <td colSpan={6}><div className="table-empty">No se encontraron contactos.</div></td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="table-footer">
           <span className="text-sm text-muted">Mostrando {rows.length} resultados</span>
           <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button className="btn-secondary btn-sm" disabled={page <= 1} onClick={() => setPage(prev => prev - 1)}>Anterior</button>
              <button className="btn-secondary btn-sm" disabled={!hasMore} onClick={() => setPage(prev => prev + 1)}>Siguiente</button>
           </div>
        </div>
      </div>

      {/* ── Modal ────────────────────────────────────────────────── */}
      {modalOpen && (
        <div className="modal-backdrop" onClick={(e) => e.target === e.currentTarget && closeModal()}>
          <div className="modal-box modal-xl">
            <div className="modal-header">
              <div>
                <h3 className="modal-header-title">{editingId ? 'Editar Contacto' : 'Nuevo Contacto'}</h3>
                <p className="text-sm text-muted">Asegúrate que los datos coincidan con Alegra</p>
              </div>
              <button className="icon-btn" onClick={closeModal}><X size={16} /></button>
            </div>
            <div className="modal-body">
              <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem' }}>
                <button
                  className={selectedType === 'client' ? 'btn-primary' : 'btn-secondary'}
                  style={{ flex: 1 }}
                  onClick={() => setForm(prev => ({ ...prev, contact_type: ['client'] }))}
                >Cliente</button>
                <button
                  className={selectedType === 'provider' ? 'btn-primary' : 'btn-secondary'}
                  style={{ flex: 1 }}
                  onClick={() => setForm(prev => ({ ...prev, contact_type: ['provider'] }))}
                >Proveedor</button>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
                <div className="grid-item" style={{ gridColumn: 'span 2' }}>
                   <label>Nombre completo o Razón social</label>
                   <input className="input" placeholder="Ej. Juan Perez o Empresa S.A.S" value={form.name} onChange={e => setForm(p => ({ ...p, name: e.target.value }))} />
                </div>
                <div>
                   <label>Tipo de identificación</label>
                   <select className="input" value={form.identification_type} onChange={e => setForm(p => ({ ...p, identification_type: e.target.value }))}>
                     {identificationTypeOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                   </select>
                </div>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                   <div style={{ flex: 3 }}>
                      <label>Número</label>
                      <input className="input" placeholder="12345678" value={form.identification} onChange={e => setForm(p => ({ ...p, identification: e.target.value }))} />
                   </div>
                   <div style={{ flex: 1 }}>
                      <label>DV</label>
                      <input className="input" placeholder="0" value={form.dv} onChange={e => setForm(p => ({ ...p, dv: e.target.value }))} />
                   </div>
                </div>
                <div>
                   <label>Tipo de persona</label>
                   <select className="input" value={form.kind_of_person} onChange={e => setForm(p => ({ ...p, kind_of_person: e.target.value }))}>
                      <option value="LEGAL_ENTITY">Persona jurídica</option>
                      <option value="PERSON_ENTITY">Persona natural</option>
                   </select>
                </div>
                <div>
                   <label>Responsabilidad tributaria</label>
                   <select className="input" value={form.regime} onChange={e => setForm(p => ({ ...p, regime: e.target.value }))}>
                      {regimeOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                   </select>
                </div>
              </div>

              <div style={{ marginTop: '1.5rem', paddingTop: '1rem', borderTop: '1px solid var(--border)', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
                 <div>
                    <label>Correo electrónico</label>
                    <input className="input" placeholder="ejemplo@correo.com" value={form.email} onChange={e => setForm(p => ({ ...p, email: e.target.value }))} />
                 </div>
                 <div>
                    <label>Teléfono</label>
                    <input className="input" placeholder="601-0000000" value={form.phone_primary} onChange={e => setForm(p => ({ ...p, phone_primary: e.target.value }))} />
                 </div>
                 <div>
                    <label>Celular</label>
                    <input className="input" placeholder="300-0000000" value={form.mobile} onChange={e => setForm(p => ({ ...p, mobile: e.target.value }))} />
                 </div>
              </div>

              <div style={{ marginTop: '1rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
                 <div>
                    <label>Dirección</label>
                    <input className="input" placeholder="Calle 123 #45-67" value={form.address} onChange={e => setForm(p => ({ ...p, address: e.target.value }))} />
                 </div>
                 <div>
                    <label>Ciudad</label>
                    <input className="input" placeholder="Bogotá" value={form.city} onChange={e => setForm(p => ({ ...p, city: e.target.value }))} />
                 </div>
                 <div>
                    <label>Departamento</label>
                    <input className="input" placeholder="Cundinamarca" value={form.department} onChange={e => setForm(p => ({ ...p, department: e.target.value }))} />
                 </div>
              </div>
            </div>
            <div className="modal-footer">
               <button className="btn-secondary" onClick={closeModal} disabled={saving}>Cancelar</button>
               <button className="btn-primary" onClick={handleSubmit} disabled={saving}>
                 <Save size={14} /> {saving ? 'Guardando...' : editingId ? 'Guardar Cambios' : 'Crear Contacto'}
               </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Confirm dialog ───────────────────────────────────────── */}
      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="Confirmar eliminación"
        message={
          deleteTarget
            ? `Vas a eliminar el contacto ${deleteTarget.name}. Esta acción no se puede deshacer.`
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
