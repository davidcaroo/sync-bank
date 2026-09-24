export const POLL_MS = 3000

export function isActiveJob(job) {
  return job?.status === 'pending' || job?.status === 'running'
}

export function acceptedJob(response) {
  return response?.data?.job || null
}

function summaryText(result) {
  const r = result || {}
  const parts = [
    `${Number(r.created || 0)} creadas`,
    `${Number(r.duplicates || 0)} duplicadas`,
    `${Number(r.invalid || 0)} inválidas`,
  ]
  if (Number(r.auto_caused || 0) > 0) parts.push(`${Number(r.auto_caused)} autocausadas`)
  if (Number(r.errors || 0) > 0) parts.push(`${Number(r.errors)} con error`)
  return parts.join(', ')
}

// Turns a persisted job into what the dashboard shows: label, tone and detail.
export function describeJob(job) {
  if (!job) return null
  if (job.status === 'pending') {
    return { label: 'En cola', tone: 'info', detail: 'La sincronización está esperando su turno.' }
  }
  if (job.status === 'running') {
    const { messages_found: found, messages_processed: done } = job.progress || {}
    return {
      label: 'Ejecutando',
      tone: 'info',
      detail: found ? `${done || 0} de ${found} correos` : 'Leyendo el buzón…',
    }
  }
  if (job.status === 'failed') {
    return {
      label: 'Falló',
      tone: 'danger',
      detail: `${job.error_message || 'Error desconocido'} (${job.attempts || 0} intentos)`,
    }
  }
  const hasErrors = Number(job.result?.errors || 0) > 0
  return {
    label: 'Terminado',
    tone: hasErrors ? 'warning' : 'success',
    detail: summaryText(job.result),
  }
}
