import { describe, expect, it } from 'vitest'
import {
  isManualServiceChargeNumber,
  stripOfficialNumberFields,
} from '../app/utils/lcs/sequences'

describe('official number stripping', () => {
  it('strips a client-supplied official number so the backend allocates it', () => {
    const input = stripOfficialNumberFields({
      quotationNo: 'CLIENT-SUPPLIED-NO',
      customer: 'Manhattan SEZ Co., Ltd.',
      status: 'Draft',
    }, 'quotations')
    expect(input.quotationNo).toBeUndefined()
  })

  it('keeps manual charge numbers for standalone service charges', () => {
    const input = {
      jobNo: '',
      chargeNo: 'SC-MANUAL-001',
      customer: 'Standalone Customer',
    }
    expect(isManualServiceChargeNumber(input)).toBe(true)
    const stripped = stripOfficialNumberFields(input, 'jobCharges')
    expect(stripped.chargeNo).toBe('SC-MANUAL-001')
  })

  it('strips charge numbers when a service order is linked', () => {
    const stripped = stripOfficialNumberFields({
      jobNo: 'LCS-IM-260821',
      chargeNo: 'SC-MANUAL-001',
      customer: 'Linked Customer',
    }, 'jobCharges')
    expect(stripped.chargeNo).toBeUndefined()
    expect(isManualServiceChargeNumber({ jobNo: 'LCS-IM-260821', chargeNo: 'SC-MANUAL-001' })).toBe(false)
  })
})
