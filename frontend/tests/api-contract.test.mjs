import assert from 'node:assert/strict'
import test from 'node:test'

import { FACTURAS_COLLECTION } from '../src/lib/endpoints.js'

test('facturas collection keeps the trailing slash required by FastAPI', () => {
  assert.equal(FACTURAS_COLLECTION, '/facturas/')
})
