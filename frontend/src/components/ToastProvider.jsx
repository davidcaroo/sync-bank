import React, { createContext, useCallback, useContext, useMemo, useState } from 'react'
import { AlertCircle, CheckCircle2, Info, TriangleAlert, X } from 'lucide-react'

const ToastContext = createContext(null)

const iconMap = {
  success: CheckCircle2,
  error: AlertCircle,
  warning: TriangleAlert,
  info: Info,
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const dismiss = useCallback((id) => {
    setToasts((prev) => prev.filter((item) => item.id !== id))
  }, [])

  const push = useCallback((message, variant = 'info', duration = 4000) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    setToasts((prev) => [...prev, { id, message, variant }])
    window.setTimeout(() => dismiss(id), duration)
  }, [dismiss])

  const api = useMemo(() => ({
    success: (msg, duration) => push(msg, 'success', duration),
    error: (msg, duration) => push(msg, 'error', duration),
    warning: (msg, duration) => push(msg, 'warning', duration),
    info: (msg, duration) => push(msg, 'info', duration),
  }), [push])

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="toast-stack" role="status" aria-live="polite">
        {toasts.map((toast) => {
          const Icon = iconMap[toast.variant] || Info
          return (
            <div key={toast.id} className={`toast-card toast-${toast.variant}`}>
              <Icon size={18} />
              <p>{toast.message}</p>
              <button type="button" onClick={() => dismiss(toast.id)} aria-label="Cerrar notificacion">
                <X size={14} />
              </button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) {
    throw new Error('useToast debe usarse dentro de ToastProvider')
  }
  return ctx
}
