import React, { useEffect, useRef, useState } from 'react'
import {
  IconFolder as Building2,
  IconArchive as Landmark,
  IconPlus as Plus,
  IconSave as Save,
  IconTrash as Trash2,
  IconRefresh,
  IconLoading,
  IconEdit,
  IconX,
  IconSearch
} from '../components/icons/Icons'
import ConfirmDialog from '../components/ConfirmDialog'
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
  nit_proveedor:    '',
  nombre_cuenta:    '',
  id_cuenta_alegra: '',
  id_retefuente:    '',
  id_reteica:       '',
  id_reteiva:       '',
  activo:           true,
}

export default function Configuracion() {
  const toast       = useToast()
  const formCardRef = useRef(null)

  const [data,          setData]          = useState([])
  const [catalogo,      setCatalogo]      = useState({ categories: [], cost_centers: [] })
  const [form,          setForm]          = useState(emptyForm)
  const [editingId,     setEditingId]     = useState(null)
  const [loading,       setLoading]       = useState(false)
  const [catalogLoading,setCatalogLoading]= useState(false)
  const [error,         setError]         = useState(null)
  const [deleteTarget,  setDeleteTarget]  = useState(null)
  const [deleteLoading, setDeleteLoading] = useState(false)

  /* ── data fetchers ─────────────────────────────────────── */
  const fetchData = async () => {
    if (!isApiConfigured) { setError('VITE_API_URL no está configurado.'); return }
    setLoading(true); setError(null)
    try {
      const response = await getConfigCuentas()
      setData(response.data || [])
    } catch {
      setError('No se pudo cargar la configuración de cuentas.')
      toast.error('No fue posible cargar la configuración guardada.')
    } finally { setLoading(false) }
  }

  const fetchCatalogo = async (refresh = false) => {
    if (!isApiConfigured) return
    setCatalogLoading(true)
    try {
      const response = await getAlegraCatalogo(refresh ? { refresh: true } : undefined)
      setCatalogo({
        categories:   response.data?.categories   || [],
        cost_centers: response.data?.cost_centers || [],
      })
    } catch {
      toast.warning('No se pudo obtener el catálogo desde Alegra.')
    } finally { setCatalogLoading(false) }
  }

  useEffect(() => { fetchData(); fetchCatalogo() }, [])

  /* ── form handlers ─────────────────────────────────────── */
  const handleCuentaChange = (value) => {
    const match = catalogo.categories.find((item) => String(item.id) === String(value))
    setForm((prev) => ({ ...prev, id_cuenta_alegra: value, nombre_cuenta: match?.name || prev.nombre_cuenta }))
  }

  const resetForm = () => { setForm(emptyForm); setEditingId(null) }

  const handleSubmit = async () => {
    setLoading(true); setError(null)
    try {
      const payload = {
        ...form,
        id_retefuente: form.id_retefuente || null,
        id_reteica:    form.id_reteica    || null,
        id_reteiva:    form.id_reteiva    || null,
      }
      if (editingId) {
        await updateConfigCuenta(editingId, payload)
      } else {
        await createConfigCuenta(payload)
      }
      resetForm(); await fetchData()
      toast.success(editingId ? 'Configuración actualizada.' : 'Mapeo creado correctamente.')
    } catch {
      setError('No se pudo guardar el registro.')
      toast.error('No se pudo guardar el mapeo de cuenta.')
    } finally { setLoading(false) }
  }

  const handleEdit = (row) => {
    setEditingId(row.id)
    setForm({
      nit_proveedor:    row.nit_proveedor    || '',
      nombre_cuenta:    row.nombre_cuenta    || '',
      id_cuenta_alegra: row.id_cuenta_alegra || '',
      id_retefuente:    row.id_retefuente    || '',
      id_reteica:       row.id_reteica       || '',
      id_reteiva:       row.id_reteiva       || '',
      activo:           row.activo ?? true,
    })
    formCardRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    toast.info(`Editando mapeo para NIT ${row.nit_proveedor}.`)
  }

  const handleToggle = async (row) => {
    try {
      await updateConfigCuenta(row.id, { activo: !row.activo })
      await fetchData()
    } catch {
      toast.error('No se pudo cambiar el estado del registro.')
    }
  }

  const handleConfirmDelete = async () => {
    if (!deleteTarget) return
    setDeleteLoading(true)
    try {
      await deleteConfigCuenta(deleteTarget.id)
      await fetchData()
      toast.success('Registro eliminado correctamente.')
    } catch {
      toast.error('No se pudo eliminar el registro seleccionado.')
    } finally { setDeleteLoading(false); setDeleteTarget(null) }
  }

  /* ── render ─────────────────────────────────────────────── */
  return (
    <div>
      {/* ── Page heading ─────────────────────────────────── */}
      <div className="page-heading">
        <div>
          <h1 className="page-heading-title">Mapa de Cuentas</h1>
          <p className="page-heading-sub">Mapeo NIT → cuentas contables en Alegra</p>
        </div>
        <button
          className="btn-secondary btn-sm"
          onClick={() => fetchCatalogo(true)}
          disabled={catalogLoading}
          style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
        >
          <IconRefresh 
            size={14} 
            style={{ animation: catalogLoading ? 'spin 1s linear infinite' : 'none' }} 
          />
          {catalogLoading ? 'Actualizando catálogo…' : 'Actualizar catálogo Alegra'}
        </button>
      </div>

      {error && <div className="ui-alert" role="alert">{error}</div>}

      {/* ── Form card ────────────────────────────────────── */}
      <div className="sb-card" ref={formCardRef}>
        <div className="sb-card-header">
          <h2 className="sb-card-header-title" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <Plus size={14} />
            {editingId ? 'Editar registro' : 'Nuevo registro'}
          </h2>
          {editingId && (
            <button 
              className="btn-secondary btn-sm" 
              onClick={resetForm}
              style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              <IconX size={14} color="#858796" /> Cancelar edición
            </button>
          )}
        </div>

        <div className="sb-card-body">
          {/* 6-field grid: 3 cols on md+ */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
              gap: '0.75rem',
              marginBottom: '1rem',
            }}
          >
            <div>
              <label htmlFor="cfg-nit">NIT Proveedor</label>
              <input
                id="cfg-nit"
                className="input"
                placeholder="900123456"
                value={form.nit_proveedor}
                onChange={(e) => setForm((p) => ({ ...p, nit_proveedor: e.target.value }))}
              />
            </div>
            <div>
              <label htmlFor="cfg-nombre">Nombre cuenta</label>
              <input
                id="cfg-nombre"
                className="input"
                placeholder="Ej. Compras nacionales"
                value={form.nombre_cuenta}
                onChange={(e) => setForm((p) => ({ ...p, nombre_cuenta: e.target.value }))}
              />
            </div>
            <div>
              <label htmlFor="cfg-cuenta">Cuenta Alegra</label>
              <select
                id="cfg-cuenta"
                className="input"
                value={form.id_cuenta_alegra}
                onChange={(e) => handleCuentaChange(e.target.value)}
              >
                <option value="">— Selecciona —</option>
                {catalogo.categories.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.code || item.id} | {item.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="cfg-retefuente">ID Retefuente</label>
              <input
                id="cfg-retefuente"
                className="input"
                placeholder="ID retención en la fuente"
                value={form.id_retefuente}
                onChange={(e) => setForm((p) => ({ ...p, id_retefuente: e.target.value }))}
              />
            </div>
            <div>
              <label htmlFor="cfg-reteica">ID Reteica</label>
              <input
                id="cfg-reteica"
                className="input"
                placeholder="ID reteica"
                value={form.id_reteica}
                onChange={(e) => setForm((p) => ({ ...p, id_reteica: e.target.value }))}
              />
            </div>
            <div>
              <label htmlFor="cfg-reteiva">ID Reteiva</label>
              <input
                id="cfg-reteiva"
                className="input"
                placeholder="ID reteiva"
                value={form.id_reteiva}
                onChange={(e) => setForm((p) => ({ ...p, id_reteiva: e.target.value }))}
              />
            </div>
          </div>

          {/* Form footer row */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.875rem', fontWeight: 700, textTransform: 'none', letterSpacing: 0 }}>
              <input
                type="checkbox"
                checked={form.activo}
                onChange={(e) => setForm((p) => ({ ...p, activo: e.target.checked }))}
              />
              Activo
            </label>

            <div style={{ display: 'flex', gap: '0.5rem' }}>
              {editingId && (
                <button className="btn-secondary btn-sm" onClick={resetForm} disabled={loading}>
                  Cancelar
                </button>
              )}
              <button className="btn-primary" onClick={handleSubmit} disabled={loading} id="btn-guardar-cuenta">
                <Save size={14} />
                {loading ? 'Guardando…' : 'Guardar mapeo'}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* ── Catálogo de Alegra – dos cards lado a lado ──── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginBottom: '1.5rem' }}
           className="catalog-grid">
        {/* Cuentas contables */}
        <div className="sb-card" style={{ marginBottom: 0 }}>
          <div className="sb-card-header">
            <h2 className="sb-card-header-title" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <Landmark size={14} /> Cuentas contables
            </h2>
            <span className="text-muted text-xs fw-bold">{catalogo.categories.length} registros</span>
          </div>
          <div
            className="table-responsive"
            style={{ maxHeight: '350px', overflowY: 'auto' }}
          >
            <table className="table-admin" style={{ minWidth: 0 }}>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Código</th>
                  <th>Nombre</th>
                </tr>
              </thead>
              <tbody>
                {catalogo.categories.map((item) => (
                  <tr key={item.id}>
                    <td className="text-muted text-sm">{item.id}</td>
                    <td className="fw-bold text-sm">{item.code || '—'}</td>
                    <td className="text-sm">{item.name}</td>
                  </tr>
                ))}
                {catalogo.categories.length === 0 && (
                  <tr>
                    <td colSpan={3}>
                      <div className="table-empty" style={{ padding: '1.5rem' }}>
                        Sin cuentas cargadas.
                      </div>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Centros de costo */}
        <div className="sb-card" style={{ marginBottom: 0 }}>
          <div className="sb-card-header">
            <h2 className="sb-card-header-title" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <Building2 size={14} /> Centros de costo
            </h2>
            <span className="text-muted text-xs fw-bold">{catalogo.cost_centers.length} registros</span>
          </div>
          <div
            className="table-responsive"
            style={{ maxHeight: '350px', overflowY: 'auto' }}
          >
            <table className="table-admin" style={{ minWidth: 0 }}>
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
                    <td className="text-muted text-sm">{item.id}</td>
                    <td className="text-sm">{item.name}</td>
                    <td className="text-sm">
                      <span className={`status-badge ${item.status === 'active' ? 'badge-success' : 'badge-muted'}`}>
                        {item.status || 'active'}
                      </span>
                    </td>
                  </tr>
                ))}
                {catalogo.cost_centers.length === 0 && (
                  <tr>
                    <td colSpan={3}>
                      <div className="table-empty" style={{ padding: '1.5rem' }}>
                        Sin centros de costo cargados.
                      </div>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* ── Registros guardados ──────────────────────────── */}
      <div className="sb-card">
        <div className="sb-card-header">
          <h2 className="sb-card-header-title">Mapeos registrados</h2>
          <span className="text-muted text-xs fw-bold">{data.length} registro{data.length !== 1 ? 's' : ''}</span>
        </div>
        <div className="table-responsive">
          <table className="table-admin" aria-label="Mapeos de cuentas">
            <thead>
              <tr>
                <th>NIT Proveedor</th>
                <th className="d-none-mobile">Proveedor</th>
                <th>Cuenta</th>
                <th className="d-none-mobile">ID Alegra</th>
                <th>Activo</th>
                <th style={{ width: '130px' }}>Acciones</th>
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
                        Cargando mapeos...
                      </p>
                    </div>
                  </td>
                </tr>
              )}
              {!loading && data.map((row) => (
                <tr key={row.id}>
                  <td className="fw-bold">{row.nit_proveedor}</td>
                  <td className="d-none-mobile text-muted">{row.nombre_proveedor || '—'}</td>
                  <td>{row.nombre_cuenta}</td>
                  <td className="d-none-mobile text-muted">{row.id_cuenta_alegra || '—'}</td>
                  <td>
                    <button
                      className={`status-badge ${row.activo ? 'badge-success' : 'badge-muted'}`}
                      onClick={(e) => { e.stopPropagation(); handleToggle(row) }}
                      title="Alternar estado"
                    >
                      {row.activo ? 'Activo' : 'Inactivo'}
                    </button>
                  </td>
                  <td>
                     <div style={{ display: 'flex', gap: '0.35rem' }}>
                      <button
                        title="Editar"
                        className="btn-secondary btn-sm"
                        onClick={(e) => { e.stopPropagation(); handleEdit(row) }}
                        style={{ display: 'flex', alignItems: 'center', gap: '4px', border: '1px solid #f6c23e', color: '#f6c23e' }}
                      >
                        <IconEdit size={14} />
                        <span className="d-none-mobile">Editar</span>
                      </button>
                      <button
                        className="btn-danger btn-sm"
                        onClick={(e) => { e.stopPropagation(); setDeleteTarget(row) }}
                        aria-label="Eliminar"
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
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
                      <p className="fw-bold">No hay mapeos configurados</p>
                      <p className="text-sm text-muted mt-1">Crea el primer mapeo en el formulario superior.</p>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Confirm dialog ───────────────────────────────── */}
      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="Confirmar eliminación"
        message={
          deleteTarget
            ? `Vas a eliminar la configuración del NIT ${deleteTarget.nit_proveedor}. Esta acción no se puede deshacer.`
            : ''
        }
        confirmLabel="Eliminar"
        cancelLabel="Cancelar"
        onConfirm={handleConfirmDelete}
        onCancel={() => setDeleteTarget(null)}
        loading={deleteLoading}
      />
    </div>
  )
}
