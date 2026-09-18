import assert from 'node:assert/strict'
import test from 'node:test'

import { describePrefill, hasMissingAccount } from '../src/lib/prefillNotice.js'

const item = (extra = {}) => ({ cuenta_contable_alegra: '5105', ...extra })

test('a manual rule is described as such', () => {
  const notice = describePrefill([item({ prefill_source: 'manual', confidence: 1 })])
  assert.match(notice.text, /regla manual/)
})

test('history shows its confidence', () => {
  const notice = describePrefill([item({ prefill_source: 'historical', confidence: 0.75 })])
  assert.match(notice.text, /historial \(75 %\)/)
})

test('an unclassified invoice warns that the account must be selected', () => {
  const notice = describePrefill([{ cuenta_contable_alegra: null }])
  assert.equal(notice.tone, 'warning')
  assert.match(notice.text, /Selecciona la cuenta/)
})

test('causation stays blocked while any item lacks an account', () => {
  assert.equal(hasMissingAccount([item(), { cuenta_contable_alegra: null }]), true)
  assert.equal(hasMissingAccount([item()]), false)
})
