import React from 'react'
import { X } from 'lucide-react'
import { StatusBadge } from './DashboardBase'

export default function FacturaModal({
  factura,
  onClose,
  onCausar,
  onItemChange,
  loading,
  categories = [],
  costCenters = [],
}) {
  if (!factura) return null

  const items = factura.items_factura || factura.items || []

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="glass w-full max-w-4xl rounded-2xl overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
          <div>
            <h3 className="text-lg font-semibold">Factura {factura.numero_factura}</h3>
            <p className="text-sm text-gray-400">{factura.nombre_proveedor}</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <X size={18} />
          </button>
        </div>

        <div className="p-6 space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
            <div className="glass px-4 py-3 rounded-xl">
              <p className="text-gray-400">CUFE</p>
              <p className="font-medium break-all">{factura.cufe || '-'}</p>
            </div>
            <div className="glass px-4 py-3 rounded-xl">
              <p className="text-gray-400">Estado</p>
              <StatusBadge status={factura.estado} />
            </div>
            <div className="glass px-4 py-3 rounded-xl">
              <p className="text-gray-400">Total</p>
              <p className="font-semibold">
                ${Number(factura.total || 0).toLocaleString()}
              </p>
            </div>
          </div>

          <div className="glass rounded-2xl overflow-hidden">
            <div className="px-6 py-3 border-b border-white/10">
              <h4 className="font-semibold">Items</h4>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="text-gray-400 border-b border-white/5">
                    <th className="px-6 py-3 font-medium">Descripcion</th>
                    <th className="px-6 py-3 font-medium">Cantidad</th>
                    <th className="px-6 py-3 font-medium">Precio</th>
                    <th className="px-6 py-3 font-medium">Cuenta Alegra</th>
                    <th className="px-6 py-3 font-medium">Centro de costo</th>
                    <th className="px-6 py-3 font-medium text-right">Total</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {items.map((item) => (
                    <tr key={item.id || `${item.descripcion}-${item.total_linea}`}>
                      <td className="px-6 py-3">{item.descripcion}</td>
                      <td className="px-6 py-3">{item.cantidad}</td>
                      <td className="px-6 py-3">${Number(item.precio_unitario || 0).toLocaleString()}</td>
                      <td className="px-6 py-3 min-w-64">
                        <select
                          className="input"
                          value={item.cuenta_contable_alegra || ''}
                          onChange={(event) => onItemChange?.(item.id, 'cuenta_contable_alegra', event.target.value)}
                        >
                          <option value="">Seleccionar cuenta</option>
                          {categories.map((cat) => (
                            <option key={cat.id} value={cat.id}>
                              {(cat.code || cat.id)} | {cat.name}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="px-6 py-3 min-w-64">
                        <select
                          className="input"
                          value={item.centro_costo_alegra || ''}
                          onChange={(event) => onItemChange?.(item.id, 'centro_costo_alegra', event.target.value)}
                        >
                          <option value="">Sin centro de costo</option>
                          {costCenters.map((center) => (
                            <option key={center.id} value={center.id}>
                              {center.id} | {center.name}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="px-6 py-3 text-right">${Number(item.total_linea || 0).toLocaleString()}</td>
                    </tr>
                  ))}
                  {items.length === 0 && (
                    <tr>
                      <td className="px-6 py-4 text-gray-400" colSpan={6}>Sin items.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between px-6 py-4 border-t border-white/10">
          <div className="text-sm text-gray-400">
            Emision: {factura.fecha_emision ? new Date(factura.fecha_emision).toLocaleDateString() : '-'}
          </div>
          <button
            onClick={onCausar}
            disabled={loading || factura.estado === 'procesado'}
            className="btn-primary"
          >
            {loading ? 'Enviando a Alegra...' : 'Causar en Alegra'}
          </button>
        </div>
      </div>
    </div>
  )
}
