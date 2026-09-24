import assert from 'node:assert/strict'
import test from 'node:test'

import { acceptedJob, describeJob, isActiveJob, POLL_MS } from '../src/lib/syncJob.js'

test('only queued or running jobs keep the dashboard polling', () => {
  assert.equal(isActiveJob({ status: 'pending' }), true)
  assert.equal(isActiveJob({ status: 'running' }), true)
  assert.equal(isActiveJob({ status: 'succeeded' }), false)
  assert.equal(isActiveJob({ status: 'failed' }), false)
  assert.equal(isActiveJob(null), false)
  assert.ok(POLL_MS >= 1000)
})

test('the accepted response of the manual trigger yields the job to follow', () => {
  const job = { id: 'j1', status: 'pending' }
  assert.deepEqual(acceptedJob({ data: { job, created: true } }), job)
  assert.deepEqual(acceptedJob({ data: { job, created: false } }), job)
  assert.equal(acceptedJob({ data: {} }), null)
  assert.equal(acceptedJob(undefined), null)
})

test('a queued job says it is waiting', () => {
  const view = describeJob({ status: 'pending' })
  assert.match(view.label, /En cola/)
  assert.equal(view.tone, 'info')
})

test('a running job shows its persisted progress', () => {
  const view = describeJob({
    status: 'running',
    progress: { messages_found: 20, messages_processed: 5 },
  })
  assert.match(view.label, /Ejecutando/)
  assert.match(view.detail, /5 de 20 correos/)
})

test('a finished job summarises what happened and warns about errors', () => {
  const ok = describeJob({
    status: 'succeeded',
    result: { created: 3, duplicates: 2, invalid: 1, auto_caused: 1, errors: 0 },
  })
  assert.equal(ok.tone, 'success')
  assert.match(ok.detail, /3 creadas, 2 duplicadas, 1 inválidas, 1 autocausadas/)

  const partial = describeJob({ status: 'succeeded', result: { created: 1, errors: 2 } })
  assert.equal(partial.tone, 'warning')
  assert.match(partial.detail, /2 con error/)
})

test('a failed job shows the last error after the retries', () => {
  const view = describeJob({ status: 'failed', error_message: 'imap down', attempts: 3 })
  assert.equal(view.tone, 'danger')
  assert.match(view.label, /Falló/)
  assert.match(view.detail, /imap down/)
  assert.match(view.detail, /3 intentos/)
})

test('no job at all is described as nothing to show', () => {
  assert.equal(describeJob(null), null)
})
