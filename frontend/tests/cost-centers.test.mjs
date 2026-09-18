import assert from 'node:assert/strict'
import test from 'node:test'

import { activeCostCenters, isActiveCostCenter } from '../src/lib/costCenters.js'

const centers = [
  { id: 1, name: 'REEXPEDICIONES', status: 'active' },
  { id: 2, name: 'REDETRANS', status: 'inactive' },
  { id: 3, name: 'SIN ESTADO' },
  { id: 4, name: 'MAYUSCULAS', status: 'ACTIVE' },
]

test('only active cost centers are listed (a missing status counts as active)', () => {
  assert.deepEqual(activeCostCenters(centers).map((c) => c.id), [1, 3, 4])
})

test('inactive is excluded and bad input is tolerated', () => {
  assert.equal(isActiveCostCenter({ status: 'inactive' }), false)
  assert.deepEqual(activeCostCenters(undefined), [])
})
