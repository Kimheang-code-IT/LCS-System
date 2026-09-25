import { describe, expect, it } from 'vitest'
import { headerChromeOwnedByCurrentRoute, headerListNavDisabled } from '../app/utils/layout/header-actions'

describe('header list nav', () => {
  it('disables previous/next on create, list ends, and while a nav request is in flight', () => {
    expect(headerListNavDisabled({
      isCreate: false,
      canNavigate: true,
      loading: false,
      direction: null,
    })).toBe(false)

    expect(headerListNavDisabled({
      isCreate: true,
      canNavigate: true,
      loading: false,
      direction: null,
    })).toBe(true)

    expect(headerListNavDisabled({
      isCreate: false,
      canNavigate: false,
      loading: false,
      direction: null,
    })).toBe(true)

    expect(headerListNavDisabled({
      isCreate: false,
      canNavigate: true,
      loading: true,
      direction: null,
    })).toBe(true)

    expect(headerListNavDisabled({
      isCreate: false,
      canNavigate: true,
      loading: false,
      direction: 'next',
    })).toBe(true)
  })
})

describe('header chrome ownership', () => {
  it('lets the next page keep the chrome it already claimed on the current route', () => {
    // Race order: the incoming page writes the title before the outgoing page unmounts.
    expect(headerChromeOwnedByCurrentRoute('/reports/operations/trial-balance', '/reports/operations/trial-balance')).toBe(true)
  })

  it('clears chrome when the leaving page belonged to a previous route', () => {
    // Normal order: the outgoing page clears after navigation already changed route.
    expect(headerChromeOwnedByCurrentRoute('/reports/operations/service-orders', '/reports/operations/trial-balance')).toBe(false)
  })

  it('clears chrome when nothing has written it yet', () => {
    expect(headerChromeOwnedByCurrentRoute('', '/reports/operations/trial-balance')).toBe(false)
  })
})

