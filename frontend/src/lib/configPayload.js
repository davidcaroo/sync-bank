export const buildConfigPayload = (form) => ({
  nit_proveedor: String(form.nit_proveedor || '').replace(/\D/g, ''),
  nombre_proveedor: String(form.nombre_proveedor || '').trim() || null,
  id_cuenta_alegra: form.id_cuenta_alegra,
  id_centro_costo_alegra: form.id_centro_costo_alegra || null,
  auto_causar: Boolean(
    form.auto_causar && form.id_cuenta_alegra && form.id_centro_costo_alegra
  ),
  activo: Boolean(form.activo),
})

// Changing what a rule applies to revokes autocausation until it is re-granted.
export const withClassificationChange = (form, field, value) => ({
  ...form,
  [field]: value,
  auto_causar: false,
})
