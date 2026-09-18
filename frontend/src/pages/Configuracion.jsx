import React, { useEffect, useMemo, useRef, useState } from 'react'
import {
  IconFolder as Building2,
  IconArchive as Landmark,
  IconPlus as Plus,
  IconSave as Save,
  IconTrash as Trash2,
  IconRefresh,
  IconEdit,
  IconX,
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
import { buildConfigPayload, withClassificationChange } from '../lib/configPayload'
import { activeCostCenters, isActiveCostCenter } from '../lib/costCenters'
import { useToast } from '../components/ToastProvider'

const emptyForm = {
  nit_proveedor: '',
  nombre_proveedor: '',
  id_cuenta_alegra: '',
  id_centro_costo_alegra: '',
  auto_causar: false,
  activo: true,
}

const SOURCE_LABELS = {
  manual: 'Manual',
  historical: 'Historial',
  alegra: 'Alegra',
  auto: 'Automático',
}

const getErrorMessage = (err, fallback) => {
  const detail = err?.response?.data?.detail
  return typeof detail === 'string' && detail.trim() ? detail : fallback
}

export default function Configuracion() {
  const toast = useToast()
  const formCardRef = useRef(null)

  const [data, setData] = useState([])
  const [catalogo, setCatalogo] = useState({ categories: [], cost_centers: [] })
  const [form, setForm] = useState(emptyForm)
  const [editingId, setEditingId] = useState(null)
  const [loading, setLoading] = useState(false)
  const [catalogLoading, setCatalogLoading] = useState(false)
  const [error, setError] = useState(null)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [deleteLoading, setDeleteLoading] = useState(false)

  const accountLabel = useMemo(() => {
    const byId = new Map(catalogo.categories.map((item) => [String(item.id), item]))
    return (id) => {
      if (!id) return '—'
      const item = byId.get(String(id))
      return item ? `${item.code || item.id} | ${item.name}` : `${id} (registrada)`
    }
  }, [catalogo.categories])

  const activeCenters = useMemo(() => activeCostCenters(catalogo.cost_centers), [catalogo.cost_centers])

  const centerLabel = useMemo(() => {
    const byId = new Map(catalogo.cost_centers.map((item) => [String(item.id), item]))
    return (id) => {
      if (!id) return 'Sin centro'
      const item = byId.get(String(id))
      if (!item) return `${id} (registrado)`
      return `${item.id} | ${item.name}${isActiveCostCenter(item) ? '' : ' (inactivo)'}`
    }
  }, [catalogo.cost_centers])

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
        categories: response.data?.categories || [],
        cost_centers: response.data?.cost_centers || [],
      })
    } catch {
      toast.warning('No se pudo obtener el catálogo desde Alegra.')
    } finally { setCatalogLoading(false) }
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { fetchData(); fetchCatalogo() }, [])

  const setClassification = (field, value) =>
    setForm((prev) => withClassificationChange(prev, field, value))

  const resetForm = () => { setForm(emptyForm); setEditingId(null) }

  const handleSubmit = async () => {
    if (!form.id_cuenta_alegra) {
      toast.warning('Selecciona la cuenta de Alegra.')
      return
    }
    setLoading(true); setError(null)
    try {
      const payload = buildConfigPayload(form)
      if (editingId) {
        await updateConfigCuenta(editingId, payload)
      } else {
        await createConfigCuenta(payload)
      }
      const wasEditing = Boolean(editingId)
      resetForm(); await fetchData()
      toast.success(wasEditing ? 'Regla actualizada.' : 'Regla creada correctamente.')
    } catch (err) {
      const message = getErrorMessage(err, 'No se pudo guardar el registro.')
      setError(message)
      toast.error(message)
    } finally { setLoading(false) }
  }

  const handleEdit = (row) => {
    setEditingId(row.id)
    setForm({
      nit_proveedor: row.nit_proveedor || '',
      nombre_proveedor: row.nombre_proveedor || '',
      id_cuenta_alegra: row.id_cuenta_alegra || '',
      id_centro_costo_alegra: row.id_centro_costo_alegra || '',
      auto_causar: Boolean(row.auto_causar),
      activo: row.activo ?? true,
    })
    formCardRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    toast.info(`Editando regla para NIT ${row.nit_proveedor}.`)
  }

  const handleToggle = async (row) => {
    try {
      await updateConfigCuenta(row.id, { activo: !row.activo })
      await fetchData()
    } catch (err) {
      toast.error(getErrorMessage(err, 'No se pudo cambiar el estado del registro.'))
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

  const canAutoCausar = Boolean(form.id_cuenta_alegra && form.id_centro_costo_alegra)
  const accountMissingFromCatalog = form.id_cuenta_alegra
    && !catalogo.categories.some((item) => String(item.id) === String(form.id_cuenta_alegra))
  const centerNotSelectable = form.id_centro_costo_alegra
    && !activeCenters.some((item) => String(item.id) === String(form.id_centro_costo_alegra))

  return (
    <div className="page-shell">
      <div className="page-heading">
        <div>
          <h1 className="page-heading-title">Mapa de Cuentas</h1>
          <p className="page-heading-sub">Reglas por proveedor (NIT): cuenta y centro de costo en Alegra</p>
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

      {error && (
        <div className="ui-alert" role="alert">
          <div><strong>No pudimos cargar o guardar el mapa de cuentas.</strong><span>{error}</span></div>
          <button type="button" className="btn-secondary btn-sm" onClick={fetchData}>Reintentar</button>
        </div>
      )}

      <div className="sb-card" ref={formCardRef}>
        <div className="sb-card-header">
          <h2 className="sb-card-header-title" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <Plus size={14} />
            {editingId ? 'Editar regla' : 'Nueva regla'}
          </h2>
          {editingId && (
            <button
              className="btn-secondary btn-sm"
              onClick={resetForm}
              style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              <IconX size={14} color="var(--muted)" /> Cancelar edición
            </button>
          )}
        </div>

        <div className="sb-card-body">
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
              gap: '0.75rem',
              marginBottom: '1rem',
            }}
          >
            <div>
              <label htmlFor="cfg-nit">NIT proveedor</label>
              <input
                id="cfg-nit"
                className="input"
                placeholder="900123456"
                value={form.nit_proveedor}
                onChange={(e) => setClassification('nit_proveedor', e.target.value)}
              />
            </div>
            <div>
              <label htmlFor="cfg-nombre">Nombre proveedor</label>
              <input
                id="cfg-nombre"
                className="input"
                placeholder="Ej. Nitido Car Wash"
                value={form.nombre_proveedor}
                onChange={(e) => setForm((p) => ({ ...p, nombre_proveedor: e.target.value }))}
              />
            </div>
            <div>
              <label htmlFor="cfg-cuenta">Cuenta Alegra</label>
              <select
                id="cfg-cuenta"
                className="input"
                value={form.id_cuenta_alegra}
                onChange={(e) => setClassification('id_cuenta_alegra', e.target.value)}
              >
                <option value="">— Selecciona —</option>
                {accountMissingFromCatalog && (
                  <option value={form.id_cuenta_alegra}>{accountLabel(form.id_cuenta_alegra)}</option>
                )}
                {catalogo.categories.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.code || item.id} | {item.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="cfg-centro">Centro de costo</label>
              <select
                id="cfg-centro"
                className="input"
                value={form.id_centro_costo_alegra}
                onChange={(e) => setClassification('id_centro_costo_alegra', e.target.value)}
              >
                <option value="">Sin centro de costo</option>
                {centerNotSelectable && (
                  <option value={form.id_centro_costo_alegra}>{centerLabel(form.id_centro_costo_alegra)}</option>
                )}
                {activeCenters.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.id} | {item.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {canAutoCausar && (
            <label
              style={{
                display: 'flex', alignItems: 'flex-start', gap: '0.5rem', marginBottom: '1rem',
                fontSize: '0.85rem', fontWeight: 600, textTransform: 'none', letterSpacing: 0,
              }}
            >
              <input
                type="checkbox"
                checked={form.auto_causar}
                onChange={(e) => setForm((p) => ({ ...p, auto_causar: e.target.checked }))}
                style={{ marginTop: '0.2rem' }}
              />
              <span>
                Autocausar en Alegra
                <span className="text-muted text-sm" style={{ display: 'block', fontWeight: 500 }}>
                  Sólo XML recibido por correo. Si una validación falla, la factura quedará pendiente.
                </span>
              </span>
            </label>
          )}

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.875rem', fontWeight: 700, textTransform: 'none', letterSpacing: 0 }}>
              <input
                type="checkbox"
                checked={form.activo}
                onChange={(e) => setForm((p) => ({ ...p, activo: e.target.checked }))}
              />
              Activa
            </label>

            <div style={{ display: 'flex', gap: '0.5rem' }}>
              {editingId && (
                <button className="btn-secondary btn-sm" onClick={resetForm} disabled={loading}>
                  Cancelar
                </button>
              )}
              <button className="btn-primary" onClick={handleSubmit} disabled={loading} id="btn-guardar-cuenta">
                <Save size={14} />
                {loading ? 'Guardando…' : 'Guardar regla'}
              </button>
            </div>
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginBottom: '1.5rem' }}
           className="catalog-grid">
        <div className="sb-card" style={{ marginBottom: 0 }}>
          <div className="sb-card-header">
            <h2 className="sb-card-header-title" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <Landmark size={14} /> Cuentas contables
            </h2>
            <span className="text-muted text-xs fw-bold">{catalogo.categories.length} registros</span>
          </div>
          <div className="table-responsive" style={{ maxHeight: '350px', overflowY: 'auto' }}>
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

        <div className="sb-card" style={{ marginBottom: 0 }}>
          <div className="sb-card-header">
            <h2 className="sb-card-header-title" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <Building2 size={14} /> Centros de costo
            </h2>
            <span className="text-muted text-xs fw-bold">{catalogo.cost_centers.length} registros</span>
          </div>
          <div className="table-responsive" style={{ maxHeight: '350px', overflowY: 'auto' }}>
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

      <div className="sb-card">
        <div className="sb-card-header">
          <h2 className="sb-card-header-title">Reglas por proveedor</h2>
          <span className="text-muted text-xs fw-bold">{data.length} regla{data.length !== 1 ? 's' : ''}</span>
        </div>
        <div className="table-responsive">
          <table className="table-admin" aria-label="Reglas por proveedor">
            <thead>
              <tr>
                <th>NIT</th>
                <th>Proveedor</th>
                <th>Cuenta</th>
                <th className="d-none-mobile">Centro de costo</th>
                <th className="d-none-mobile">Origen</th>
                <th className="d-none-mobile">Autocausa</th>
                <th>Estado</th>
                <th style={{ width: '130px' }}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                Array.from({ length: 5 }).map((_, index) => (
                  <tr key={`loading-${index}`} aria-hidden="true">
                    <td><span className="skeleton skeleton-line skeleton-line-short" /></td>
                    <td><span className="skeleton skeleton-line" /></td>
                    <td><span className="skeleton skeleton-line" /></td>
                    <td className="d-none-mobile"><span className="skeleton skeleton-line" /></td>
                    <td className="d-none-mobile"><span className="skeleton skeleton-chip" /></td>
                    <td className="d-none-mobile"><span className="skeleton skeleton-chip" /></td>
                    <td><span className="skeleton skeleton-chip" /></td>
                    <td><span className="skeleton skeleton-line skeleton-line-short" /></td>
                  </tr>
                ))
              )}
              {!loading && data.map((row) => (
                <tr key={row.id}>
                  <td className="fw-bold">{row.nit_proveedor}</td>
                  <td className="text-muted">{row.nombre_proveedor || '—'}</td>
                  <td className="text-sm">{accountLabel(row.id_cuenta_alegra)}</td>
                  <td className="d-none-mobile text-sm">{centerLabel(row.id_centro_costo_alegra)}</td>
                  <td className="d-none-mobile">
                    <span className="status-badge badge-info">{SOURCE_LABELS[row.source] || row.source || '—'}</span>
                  </td>
                  <td className="d-none-mobile">
                    <span className={`status-badge ${row.auto_causar ? 'badge-warning' : 'badge-muted'}`}>
                      {row.auto_causar ? 'Sí' : 'No'}
                    </span>
                  </td>
                  <td>
                    <button
                      className={`status-badge ${row.activo ? 'badge-success' : 'badge-muted'}`}
                      onClick={(e) => { e.stopPropagation(); handleToggle(row) }}
                      title="Alternar estado"
                    >
                      {row.activo ? 'Activa' : 'Inactiva'}
                    </button>
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: '0.35rem' }}>
                      <button
                        title="Editar"
                        className="btn-secondary btn-sm"
                        onClick={(e) => { e.stopPropagation(); handleEdit(row) }}
                        style={{ display: 'flex', alignItems: 'center', gap: '4px', border: '1px solid var(--warning)', color: 'var(--warning)' }}
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
                  <td colSpan={8}>
                    <div className="table-empty">
                      <div className="table-empty-icon" style={{ opacity: 0.2 }}>
                        <Landmark size={48} />
                      </div>
                      <p className="fw-bold">No hay reglas configuradas</p>
                      <p className="text-sm text-muted mt-1">Crea la primera regla en el formulario superior.</p>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="Confirmar eliminación"
        message={
          deleteTarget
            ? `Vas a eliminar la regla del NIT ${deleteTarget.nit_proveedor}. Esta acción no se puede deshacer.`
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
