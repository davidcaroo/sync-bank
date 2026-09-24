const RULE_SOURCES = new Set(['manual', 'config'])
const LEARNED_SOURCES = new Set(['historical', 'alegra', 'auto'])

export function hasMissingAccount(items) {
  return (items || []).some((item) => !item.cuenta_contable_alegra)
}

// Explains where the suggested classification came from so the operator reviews it.
export function describePrefill(items) {
  if (!items || items.length === 0) return null
  const classified = items.filter((item) => item.cuenta_contable_alegra)
  if (classified.length === 0) {
    return {
      tone: 'warning',
      text: 'Sin clasificación sugerida. Selecciona la cuenta contable antes de causar.',
    }
  }

  const { prefill_source: source, confidence } = classified[0]
  if (RULE_SOURCES.has(source)) {
    return {
      tone: 'info',
      text: 'Clasificación sugerida por regla manual. Revisa cuenta y centro antes de causar.',
    }
  }
  if (source === 'sugerida') {
    const percent = Number.isFinite(Number(confidence)) && confidence !== null
      ? ` (${Math.round(Number(confidence) * 100)} %)`
      : ''
    return {
      tone: 'warning',
      text: `Sugerencia de baja confianza${percent}: es la cuenta más usada con este proveedor, sin ser mayoría clara. Verifica cuenta y centro antes de causar.`,
    }
  }
  if (LEARNED_SOURCES.has(source)) {
    const percent = Number.isFinite(Number(confidence)) && confidence !== null
      ? ` (${Math.round(Number(confidence) * 100)} %)`
      : ''
    return {
      tone: 'info',
      text: `Clasificación sugerida por historial${percent}. Revisa antes de causar.`,
    }
  }
  return null
}
