import { describe, expect, it } from 'vitest'
import { enrichJobListRows } from '../app/utils/freight/job-list'

describe('job list metrics', () => {
  it('counts containers, completed tasks, and charge totals per job', () => {
    const rows = enrichJobListRows(
      [{ id: 'job-1', jobNo: 'LCS-1' }, { id: 'job-2', jobNo: 'LCS-2' }],
      {
        containers: [
          { id: 'c1', jobNo: 'LCS-1' },
          { id: 'c2', jobNo: 'LCS-1' },
        ],
        tasks: [
          { id: 't1', jobNo: 'LCS-1', status: 'COMPLETED' },
          { id: 't2', jobNo: 'LCS-1', status: 'OPEN' },
        ],
        charges: [
          { id: 'ch1', jobNo: 'LCS-1', total: 10.5 },
          { id: 'ch2', jobNo: 'LCS-1', amount: 1.5 },
        ],
      },
    )
    expect(rows[0]).toMatchObject({
      containersCount: 2,
      tasksProgress: '1 / 2',
      chargesTotal: 12,
    })
    expect(rows[1]).toMatchObject({
      containersCount: 0,
      tasksProgress: '',
      chargesTotal: '',
    })
  })

  it('counts one container with several payments on the same B/L and truck', () => {
    const rows = enrichJobListRows(
      [{
        id: 'job-1',
        jobNo: 'LCS-1',
        vatRate: 10,
        containerPayments: [
          { blNo: 'BL-1', truckNo: '3C-1', quantity: 1, description: 'Trucking', amount: 100 },
          { blNo: 'BL-1', truckNo: '3C-1', quantity: 1, description: 'Clearance', amount: 20 },
        ],
      }],
      { containers: [], tasks: [], charges: [] },
    )
    expect(rows[0]).toMatchObject({
      containersCount: 1,
      chargesTotal: 132,
    })
  })
})
