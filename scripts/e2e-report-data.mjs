#!/usr/bin/env node
/**
 * Fixture for the browser report journeys (`frontend/e2e/reports-generate.spec.ts`).
 *
 * It provisions a non-production stack with the minimum ledger a Trial Balance
 * needs and nothing else:
 *
 *   1. first-run setup (skipped when the stack already has users)
 *   2. four chart-of-accounts rows
 *   3. two posted journals — 1,000.00 revenue and 250.00 transport expense
 *
 * Every amount is fixed, so a browser assertion and a CSV can be reconciled.
 * Point it at a disposable stack only; it writes business data.
 *
 *   node scripts/e2e-report-data.mjs http://localhost:18080
 *
 * The API is reached through the same origin nginx proxies (`/api/v1`).
 */
const base = (process.argv[2] || process.env.E2E_BASE_URL || 'http://localhost').replace(/\/$/, '')
const credentials = {
  username: process.env.E2E_USERNAME || 'e2e',
  password: process.env.E2E_PASSWORD || 'Report-E2E-Passw0rd!1',
}
const email = credentials.username.includes('@') ? credentials.username : `${credentials.username}@example.test`

let csrf = ''

async function api(path, { method = 'GET', body, token } = {}) {
  const headers = { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' }
  if (csrf) headers['X-CSRF-Token'] = csrf
  if (token) headers.Authorization = `Bearer ${token}`
  const response = await fetch(`${base}/api/v1${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const setCookie = response.headers.getSetCookie?.() ?? []
  for (const cookie of setCookie) {
    const match = /csrf_token=([^;]+)/.exec(cookie)
    if (match) csrf = match[1]
  }
  const text = await response.text()
  let payload = null
  try {
    payload = text ? JSON.parse(text) : null
  }
  catch {
    payload = { raw: text }
  }
  if (!response.ok) {
    throw new Error(`${method} ${path} -> ${response.status} ${JSON.stringify(payload)}`)
  }
  return payload
}

async function ensureAdmin() {
  try {
    await api('/auth/setup/initialize', {
      method: 'POST',
      body: { email, password: credentials.password, name: 'E2E Report Admin', username: credentials.username },
    })
    console.log(`setup: created ${credentials.username}`)
  }
  catch (error) {
    if (!String(error.message).includes('409') && !String(error.message).includes('ALREADY')) throw error
    console.log('setup: already provisioned')
  }
}

async function main() {
  const ready = await fetch(`${base}/health`)
  if (!ready.ok) throw new Error(`stack is not healthy at ${base}`)

  await ensureAdmin()
  const login = await api('/auth/login', {
    method: 'POST',
    body: { username: credentials.username, password: credentials.password },
  })
  const token = login.data.access_token
  console.log(`login: ${credentials.username}`)

  const accounts = [
    { accountCode: '1020', accountName: 'Bank Account', accountType: 'ASSET', normalBalance: 'DEBIT' },
    { accountCode: '1100', accountName: 'Accounts Receivable', accountType: 'ASSET', normalBalance: 'DEBIT' },
    { accountCode: '4010', accountName: 'Service Revenue', accountType: 'REVENUE', normalBalance: 'CREDIT' },
    { accountCode: '5010', accountName: 'Transport Expense', accountType: 'EXPENSE', normalBalance: 'DEBIT' },
  ]
  for (const account of accounts) {
    try {
      await api('/chart-of-accounts', { method: 'POST', body: account, token })
      console.log(`account: ${account.accountCode}`)
    }
    catch (error) {
      console.log(`account: ${account.accountCode} already exists`)
    }
  }

  const today = new Date().toISOString().slice(0, 10)
  const journals = [
    {
      description: 'E2E report fixture revenue',
      lines: [
        { accountCode: '1100', debitAmount: '1000.0000', creditAmount: '0' },
        { accountCode: '4010', debitAmount: '0', creditAmount: '1000.0000' },
      ],
    },
    {
      description: 'E2E report fixture expense',
      lines: [
        { accountCode: '5010', debitAmount: '250.0000', creditAmount: '0' },
        { accountCode: '1020', debitAmount: '0', creditAmount: '250.0000' },
      ],
    },
  ]
  for (const journal of journals) {
    const created = await api('/journal-entries', {
      method: 'POST',
      token,
      body: { entryDate: today, postingDate: today, entryType: 'MANUAL', ...journal },
    })
    await api(`/journal-entries/${created.data.id}/post`, { method: 'POST', body: {}, token })
    console.log(`journal: posted ${created.data.entryNo}`)
  }

  const report = await api('/reports/trial-balance/generate', {
    method: 'POST',
    token,
    body: { fromDate: today, toDate: today },
  })
  if (report.data.balanced !== true) throw new Error('fixture ledger does not balance')
  console.log(`report: ${report.data.items.length} accounts, balanced`)
}

main().catch((error) => {
  console.error(error.message)
  process.exit(1)
})
