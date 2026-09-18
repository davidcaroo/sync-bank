import React from 'react'
import { IconChevronLeft, IconChevronRight } from './icons/Icons'

function buildPageList(page, totalPages) {
  const pages = new Set([1, totalPages, page - 1, page, page + 1])
  const sorted = [...pages].filter((p) => p >= 1 && p <= totalPages).sort((a, b) => a - b)

  const withGaps = []
  sorted.forEach((p, idx) => {
    if (idx > 0 && p - sorted[idx - 1] > 1) withGaps.push('...')
    withGaps.push(p)
  })
  return withGaps
}

export default function Pagination({ page, totalPages, onChange }) {
  if (!totalPages || totalPages <= 1) return null
  const items = buildPageList(page, totalPages)

  return (
    <nav className="pagination" aria-label="Paginación">
      <button
        className="btn-secondary btn-sm"
        disabled={page <= 1}
        onClick={() => onChange(page - 1)}
        aria-label="Página anterior"
      >
        <IconChevronLeft size={14} /> Anterior
      </button>

      <div className="pagination-pages">
        {items.map((item, idx) => (
          item === '...' ? (
            <span key={`gap-${idx}`} className="pagination-ellipsis">…</span>
          ) : (
            <button
              key={item}
              type="button"
              className={`pagination-page${item === page ? ' active' : ''}`}
              onClick={() => onChange(item)}
              aria-current={item === page ? 'page' : undefined}
            >
              {item}
            </button>
          )
        ))}
      </div>

      <button
        className="btn-secondary btn-sm"
        disabled={page >= totalPages}
        onClick={() => onChange(page + 1)}
        aria-label="Página siguiente"
      >
        Siguiente <IconChevronRight size={14} />
      </button>
    </nav>
  )
}
