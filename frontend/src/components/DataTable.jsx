import React from 'react'

export default function DataTable({ columns, data, onRowClick, loading, emptyLabel }) {
  return (
    <div className="panel-card">
      <div className="overflow-x-auto">
        <table className="table-admin">
          <thead>
            <tr>
              {columns.map((col) => (
                <th key={col.key}>
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td className="px-6 py-6 text-sm" colSpan={columns.length}>
                  Cargando...
                </td>
              </tr>
            )}
            {!loading && data.length === 0 && (
              <tr>
                <td className="px-6 py-6 text-sm" colSpan={columns.length}>
                  {emptyLabel || 'Sin registros.'}
                </td>
              </tr>
            )}
            {!loading && data.map((row) => (
              <tr
                key={row.id || row.mensaje_id || JSON.stringify(row)}
                className={onRowClick ? 'table-row-hover text-sm' : 'text-sm'}
                onClick={() => onRowClick?.(row)}
              >
                {columns.map((col) => (
                  <td key={col.key} className="px-6 py-4">
                    {col.render ? col.render(row) : row[col.key]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
