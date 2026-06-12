import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'

function read(path) {
  return readFileSync(new URL(path, import.meta.url), 'utf8')
}

test('commercial routes are registered', () => {
  const app = read('./App.tsx')
  assert.match(app, /path="\/terms"/)
  assert.match(app, /path="\/privacy"/)
  assert.match(app, /path="app\/onboarding"|path="onboarding"/)
  assert.match(app, /NotFoundPage/)
})

test('onboarding checklist covers trading safety steps', () => {
  const checklist = read('./components/OnboardingChecklist.tsx')
  assert.match(checklist, /连接交易所/)
  assert.match(checklist, /模拟盘/)
  assert.match(checklist, /预算纪律/)
  assert.match(checklist, /订阅/)
})

test('health and task run surfaces are wired', () => {
  const layout = read('./components/Layout.tsx')
  const settings = read('./pages/SettingsPage.tsx')
  assert.match(layout, /HealthPill/)
  assert.match(settings, /fetchTaskRuns/)
  assert.match(settings, /TaskRunTimeline/)
})
