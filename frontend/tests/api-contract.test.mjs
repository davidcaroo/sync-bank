import assert from 'node:assert/strict'
import test from 'node:test'

import {
  FACTURAS_COLLECTION,
  CONTACTOS_COLLECTION,
  CONFIG_COLLECTION,
  LOGS_COLLECTION,
} from '../src/lib/endpoints.js'

test('collection endpoints keep the trailing slash required by FastAPI', () => {
  assert.equal(FACTURAS_COLLECTION, '/facturas/')
  assert.equal(CONTACTOS_COLLECTION, '/contactos/')
  assert.equal(CONFIG_COLLECTION, '/config/')
  assert.equal(LOGS_COLLECTION, '/logs/')
})
