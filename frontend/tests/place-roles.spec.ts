/**
 * "Place Roles" is the administrator-managed vocabulary a route stop selects
 * from. The route location is free text, so there is no separate Places master.
 *
 * The role used to be a fixed `PLACE_ROLES` code list and the route location was
 * free text. The role is now database-driven. These tests pin that separation.
 */
import { describe, expect, it } from 'vitest'
import { getFreightModule } from '../app/config/freight-modules'
import { JOB_ROUTE_TABLE } from '../app/config/job-workspace-forms'
import { QUOTATION_ROUTE_TABLE } from '../app/config/route-stop-table'
import { referenceOptionSource } from '../app/utils/freight/reference-options'

const placeRoles = getFreightModule('/master-data/place-roles')!
const quotation = getFreightModule('/quotations')!

const routeTable = (module: { tables?: Array<{ key: string, columns: Array<{ key: string }> }> }) =>
  module.tables!.find(table => table.key === 'places')!

describe('place roles master data', () => {
  it('is an administrator-managed master-data page', () => {
    expect(placeRoles.path).toBe('/master-data/place-roles')
    expect(placeRoles.group).toBe('master')
    expect(placeRoles.collection).toBe('placeRoles')
    expect(placeRoles.canCreate).toBe(true)
  })

  it('carries code, name, description, order and status', () => {
    expect(placeRoles.fields.map(field => field.key)).toEqual([
      'code',
      'name',
      'sortOrder',
      'description',
      'status',
    ])
    expect(placeRoles.columns.map(column => column.key)).toEqual([
      'code',
      'name',
      'sortOrder',
      'description',
      'status',
    ])
  })

  it('ships no hardcoded role options; the records are the vocabulary', () => {
    const code = placeRoles.fields.find(field => field.key === 'code')
    expect(code?.type).toBe('text')
    expect(referenceOptionSource('placeRoleId')?.collection).toBe('placeRoles')
  })
})

describe('route tables use the same dynamic selection logic', () => {
  it('binds the quotation route to role ids and free-text locations', () => {
    const role = routeTable(quotation).columns.find(item => item.key === 'placeRoleId')
    const place = routeTable(quotation).columns.find(item => item.key === 'place')
    expect(role).toMatchObject({ type: 'select', required: true })
    expect(role?.options).toBeUndefined()
    expect(place).toMatchObject({ type: 'text' })
    expect(place?.required).toBeUndefined()
    expect(QUOTATION_ROUTE_TABLE).toBe(routeTable(quotation))
  })

  it('reads the same way on the service order route', () => {
    expect(JOB_ROUTE_TABLE.columns.some(column => column.key === 'placeRoleId')).toBe(true)
    expect(JOB_ROUTE_TABLE.columns.some(column => column.key === 'place')).toBe(true)
    expect(JOB_ROUTE_TABLE.columns.some(column => column.key === 'placeId')).toBe(false)
    expect(JOB_ROUTE_TABLE.columns.some(column => column.key === 'actual')).toBe(true)
    expect(JOB_ROUTE_TABLE.columns.some(column => column.options?.length)).toBe(false)
  })
})
