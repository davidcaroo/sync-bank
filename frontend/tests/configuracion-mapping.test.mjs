import assert from 'node:assert/strict'
import test from 'node:test'

import { buildConfigPayload, withClassificationChange } from '../src/lib/configPayload.js'

const form = {
  nit_proveedor: '900.123.456',
  nombre_proveedor: ' Nitido Car Wash ',
  id_cuenta_alegra: '5105',
  id_centro_costo_alegra: '12',
  auto_causar: true,
  activo: true,
}

test('payload only carries fields the backend supports', () => {
  assert.deepEqual(buildConfigPayload(form), {
    nit_proveedor: '900123456',
    nombre_proveedor: 'Nitido Car Wash',
    id_cuenta_alegra: '5105',
    id_centro_costo_alegra: '12',
    auto_causar: true,
    activo: true,
  })
})

test('autocausation is dropped unless both account and cost center are set', () => {
  assert.equal(
    buildConfigPayload({ ...form, id_centro_costo_alegra: '' }).auto_causar,
    false
  )
  assert.equal(
    buildConfigPayload({ ...form, id_centro_costo_alegra: '' }).id_centro_costo_alegra,
    null
  )
})

test('changing NIT, account or cost center resets autocausation', () => {
  for (const field of ['nit_proveedor', 'id_cuenta_alegra', 'id_centro_costo_alegra']) {
    assert.equal(withClassificationChange(form, field, 'x').auto_causar, false)
  }
})
