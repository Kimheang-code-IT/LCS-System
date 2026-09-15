import type { FreightRecord } from '~/types/freight/record'

const DAY_MS = 86_400_000

/** Whole days between a date and now (floored at 0; unparsable dates count as 0). */
export function daysSince(value: unknown) {
  const time = new Date(String(value || '')).getTime()
  return Number.isNaN(time) ? 0 : Math.max(0, Math.floor((Date.now() - time) / DAY_MS))
}

/** AR/AP aging bucket key for i18n `freight.dashboard.aging.*`. */
export function agingBucketKey(value: unknown) {
  const days = daysSince(value)
  if (days <= 0) return 'not_due'
  if (days <= 30) return 'd1_30'
  if (days <= 60) return 'd31_60'
  if (days <= 90) return 'd61_90'
  return 'd90_plus'
}

type Translate = (key: string) => string
type TranslateExists = (key: string) => boolean

export function labelAgingBucket(
  key: string,
  t: Translate,
  te: TranslateExists,
) {
  const i18nKey = key === 'not_due' ? 'freight.dashboard.aging.notDue' : `freight.dashboard.aging.${key}`
  return te(i18nKey) ? String(t(i18nKey)) : key.replaceAll('_', ' ')
}

/** Localized aging label for a due date. */
export function agingBucket(value: unknown, t: Translate, te: TranslateExists) {
  return labelAgingBucket(agingBucketKey(value), t, te)
}

/** First known date on a report row, normalized to `YYYY-MM-DD` for range filters and exports. */
export function reportRowDate(row: FreightRecord) {
  return String(row.postingDate || row.invoiceDate || row.billDate || row.date || row.createdAt || '').slice(0, 10)
}

/** Flatten POSTED journals into ledger lines with one global running balance. */
export function postedJournalLines(journals: FreightRecord[], accounts: FreightRecord[]): FreightRecord[] {
  const accountMap = new Map(accounts.map(row => [String(row.accountCode), row]))
  let running = 0
  return journals
    .filter(journal => String(journal.status).toUpperCase() === 'POSTED')
    .flatMap(journal =>
      (Array.isArray(journal.lines) ? journal.lines as FreightRecord[] : []).map((line, index) => {
        const debit = Number(line.debit_amount || line.debit || 0)
        const credit = Number(line.credit_amount || line.credit || 0)
        running += debit - credit
        const accountCode = String(line.account_code || line.accountCode || '')
        const account = accountMap.get(accountCode)
        return {
          ...line,
          id: `${journal.id}-${index}`,
          postingDate: journal.postingDate,
          journalNo: journal.entryNo,
          sourceDocument: journal.sourceDocumentNo,
          accountCode,
          account: account ? `${accountCode} · ${account.accountName}` : accountCode,
          accountName: account?.accountName || accountCode,
          accountType: account?.accountType || '',
          description: line.description || journal.description,
          party: line.party || '',
          jobNo: line.serviceOrder || journal.jobNo,
          branchName: line.branch || journal.branchName,
          currency: line.currency || 'USD',
          debit,
          credit,
          runningBalance: Number(running.toFixed(2)),
        } as FreightRecord
      }),
    )
}

export interface StatementGroup {
  type: string
  rows: Array<{ name: string, amount: number }>
  total: number
}

/** ERPNext-style statement section (P&L / Balance Sheet) built from typed ledger lines. */
export function buildStatementGroups(lines: FreightRecord[], types: string[]): StatementGroup[] {
  return types.map((type) => {
    const amounts = new Map<string, number>()
    for (const row of lines.filter(row => row.accountType === type)) {
      const amount = ['Revenue', 'Liability', 'Equity'].includes(type)
        ? Number(row.credit) - Number(row.debit)
        : Number(row.debit) - Number(row.credit)
      amounts.set(String(row.account), Number(amounts.get(String(row.account)) || 0) + amount)
    }
    return {
      type,
      rows: [...amounts].map(([name, amount]) => ({ name, amount })),
      total: [...amounts.values()].reduce((sum, n) => sum + n, 0),
    }
  })
}

/** Net of the first two group totals, minus the third when balancing a balance sheet. */
export function statementDifference(groups: StatementGroup[], subtractThird = false) {
  const first = Number(groups[0]?.total || 0)
  const second = Number(groups[1]?.total || 0)
  const third = subtractThird ? Number(groups[2]?.total || 0) : 0
  return first - second - third
}
