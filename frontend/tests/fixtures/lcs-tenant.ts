export const LCS_ORG_ID = 1
export const DEMO_ORG_ID = 2

export const BRANCH_BAVET_ID = 1
export const BRANCH_PP_ID = 2
export const BRANCH_DEMO_ID = 3

export const LCS_ORGANIZATIONS = [
  {
    id: LCS_ORG_ID,
    organization_code: 'LCS',
    legal_name: 'LCS Freight Forwarding Co., Ltd.',
    display_name: 'LCS Freight',
    default_currency_code: 'USD',
    timezone: 'Asia/Phnom_Penh',
    status: 'ACTIVE',
  },
  {
    id: DEMO_ORG_ID,
    organization_code: 'DEMO',
    legal_name: 'Demo Logistics Ltd.',
    display_name: 'Demo Logistics',
    default_currency_code: 'USD',
    timezone: 'Asia/Phnom_Penh',
    status: 'ACTIVE',
  },
] as const

export const LCS_BRANCHES = [
  {
    id: BRANCH_BAVET_ID,
    organization_id: LCS_ORG_ID,
    branch_code: 'BAV',
    name: 'Bavet',
    is_head_office: false,
    status: 'ACTIVE',
  },
  {
    id: BRANCH_PP_ID,
    organization_id: LCS_ORG_ID,
    branch_code: 'PNH',
    name: 'Phnom Penh',
    is_head_office: true,
    status: 'ACTIVE',
  },
  {
    id: BRANCH_DEMO_ID,
    organization_id: DEMO_ORG_ID,
    branch_code: 'HQ',
    name: 'Demo HQ',
    is_head_office: true,
    status: 'ACTIVE',
  },
] as const
