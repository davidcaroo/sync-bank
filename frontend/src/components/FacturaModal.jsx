import React from 'react'
import { X } from 'lucide-react'
import { StatusBadge } from './DashboardBase'

export default function FacturaModal({
  factura,
  onClose,
  onCausar,
  onItemChange,
  loading,
  categories  = [],
  costCenters = [],
}) {
  if (!factura) return null

  const items = factura.items_factura || factura.items || []

  return (
    <div
      className="modal-backdrop"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
      role="dialog"
      aria-modal="true"
      aria-label={`Detalle factura ${factura.numero_factura}`}
    >
      <div className="modal-box modal-xl">

        {/* ── Modal header ─────────────────────────────────────── */}
        <div className="modal-header">
          <div>
            <h3 className="modal-header-title">
              Factura {factura.numero_factura}
            </h3>
            <p className="text-sm text-muted" style={{ marginTop: '0.1rem' }}>
              {factura.nombre_proveedor}
            </p>
          </div>
          <button
            onClick={onClose}
            className="icon-btn"
            aria-label="Cerrar modal"
          >
            <X size={16} />
          </button>
        </div>

        {/* ── Modal body ───────────────────────────────────────── */}
        <div className="modal-body">

          {/* Meta grid – CUFE / NIT / Estado / Total */}
          <div className="meta-grid">
            <div className="meta-item">
              <p className="meta-label">CUFE</p>
              <p className="meta-value" style={{ fontSize: '0.72rem', wordBreak: 'break-all' }}>
                {factura.cufe || '—'}
              </p>
            </div>
            <div className="meta-item">
              <p className="meta-label">NIT Proveedor</p>
              <p className="meta-value">{factura.nit_proveedor || '—'}</p>
            </div>
            <div className="meta-item">
              <p className="meta-label">NIT Receptor</p>
              <p className="meta-value">{factura.nit_receptor || '—'}</p>
            </div>
            <div className="meta-item">
              <p className="meta-label">Estado</p>
              <div style={{ marginTop: '0.2rem' }}>
                <StatusBadge status={factura.estado} />
              </div>
            </div>
            <div className="meta-item">
              <p className="meta-label">Total</p>
              <p className="meta-value" style={{ color: 'var(--accent)' }}>
                ${Number(factura.total || 0).toLocaleString('es-CO')}
              </p>
            </div>
          </div>

          {/* Items table */}
          <div style={{
            border: '1px solid var(--border)',
            borderRadius: '0.375rem',
            overflow: 'hidden',
          }}>
            <div
              style={{
                padding: '0.65rem 1rem',
                borderBottom: '1px solid var(--border)',
                background: 'var(--panel-soft)',
              }}
            >
              <p style={{
                fontSize: '0.68rem',
                fontWeight: 800,
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
                color: 'var(--muted)',
                margin: 0,
              }}>
                Ítems de la factura
              </p>
            </div>

            <div className="table-responsive">
              <table
                className="table-admin"
                style={{ minWidth: '700px' }}
                aria-label="Ítems de la factura"
              >
                <thead>
                  <tr>
                    <th style={{ width: '30%' }}>Descripción</th>
                    <th style={{ width: '7%'  }}>Cant.</th>
                    <th style={{ width: '12%' }}>Precio</th>
                    <th style={{ width: '22%' }}>Cuenta Alegra</th>
                    <th style={{ width: '20%' }}>Centro de costo</th>
                    <th style={{ width: '9%', textAlign: 'right' }}>Total</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr key={item.id || `${item.descripcion}-${item.total_linea}`}>
                      <td style={{ maxWidth: '220px' }}>
                        <span style={{
                          display: 'block',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}>
                          {item.descripcion}
                        </span>
                      </td>
                      <td>{item.cantidad}</td>
                      <td>${Number(item.precio_unitario || 0).toLocaleString('es-CO')}</td>

                      {/* Cuenta Alegra */}
                      <td>
                        <select
                          className="input"
                          style={{ minWidth: 0, width: '100%', fontSize: '0.8rem', padding: '0.3rem 0.5rem' }}
                          value={item.cuenta_contable_alegra || ''}
                          onChange={(e) =>
                            onItemChange?.(item.id, 'cuenta_contable_alegra', e.target.value)
                          }
                        >
                          <option value="">— Cuenta —</option>
                          {categories.map((cat) => (
                            <option key={cat.id} value={cat.id}>
                              {cat.code || cat.id} | {cat.name}
                            </option>
                          ))}
                        </select>
                      </td>

                      {/* Centro de costo */}
                      <td>
                        <select
                          className="input"
                          style={{ minWidth: 0, width: '100%', fontSize: '0.8rem', padding: '0.3rem 0.5rem' }}
                          value={item.centro_costo_alegra || ''}
                          onChange={(e) =>
                            onItemChange?.(item.id, 'centro_costo_alegra', e.target.value)
                          }
                        >
                          <option value="">Sin centro</option>
                          {costCenters.map((cc) => (
                            <option key={cc.id} value={cc.id}>
                              {cc.id} | {cc.name}
                            </option>
                          ))}
                        </select>
                      </td>

                      <td style={{ textAlign: 'right', fontWeight: 700 }}>
                        ${Number(item.total_linea || 0).toLocaleString('es-CO')}
                      </td>
                    </tr>
                  ))}

                  {items.length === 0 && (
                    <tr>
                      <td colSpan={6}>
                        <div className="table-empty" style={{ padding: '1.5rem' }}>
                          Sin ítems registrados.
                        </div>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* ── Modal footer ─────────────────────────────────────── */}
        <div className="modal-footer">
          <div className="text-sm text-muted">
            <span className="text-upper fw-xbold" style={{ marginRight: '0.4rem', fontSize: '0.65rem' }}>
              Emisión:
            </span>
            {factura.fecha_emision
              ? new Date(factura.fecha_emision).toLocaleDateString('es-CO', {
                  day: '2-digit', month: 'long', year: 'numeric',
                })
              : '—'}
          </div>

          <button
            onClick={onCausar}
            disabled={loading || factura.estado === 'procesado' || factura.estado === 'causado' || factura.estado === 'duplicado'}
            className="btn-success"
            id="btn-causar-alegra"
          >
            {loading ? 'Enviando a Alegra…' : 'Causar en Alegra'}
          </button>
        </div>
      </div>
    </div>
  )
}
