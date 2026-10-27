/**
 * The route-stop table, shared by the quotation and the service-order Route tabs.
 *
 * Both forms render the same cells through `AppLineTable`; only the service order
 * adds actual-time tracking. Keeping the definition here means a change to the
 * role/location columns cannot land on one document and miss the other.
 *
 * The role column binds to the live Place Roles master. The location is free text,
 * so a route still describes where it happens without a separate Places master.
 * The `#` column rendered by the table is the sequence; the server renumbers from
 * array order on save, so a stale or duplicated client sequence cannot be stored.
 */
import type { FreightLineColumn, FreightTable } from './freight-modules'
import { routePlaceRowDefaults } from '~/utils/table/line-table-rules'

function routeColumns(withActual: boolean): FreightLineColumn[] {
  const columns: FreightLineColumn[] = [
    {
      key: 'placeRoleId',
      label: 'Place Role',
      labelKey: 'freight.ui.routeRole',
      type: 'select',
      required: true,
      width: 176,
    },
    {
      key: 'place',
      label: 'Location',
      labelKey: 'freight.ui.cols.location',
      type: 'text',
      required: true,
      width: 220,
    },
    {
      key: 'planned',
      label: 'Planned',
      labelKey: 'freight.ui.plannedCol',
      type: 'datetime',
      width: 176,
    },
  ]
  if (withActual) {
    columns.push({
      key: 'actual',
      label: 'Actual',
      labelKey: 'freight.ui.actualCol',
      type: 'datetime',
      width: 176,
    })
  }
  columns.push(
    {
      key: 'notes',
      label: 'Notes',
      labelKey: 'freight.ui.cols.notes',
      type: 'note',
    },
    // Sequence is the `#` column; the arrows persist a new order by rewriting
    // the array, which the server turns into 1..n sequence numbers.
    { key: '_order', label: '', type: 'reorder' },
    { key: 'trust', label: '', type: 'delete' },
  )
  return columns
}

/** Quotation Route tab: sequence, role, location, planned, notes, actions. */
export const QUOTATION_ROUTE_TABLE: FreightTable = {
  key: 'places',
  title: 'Route',
  titleKm: 'ផ្លូវ',
  addLabel: 'Add Route',
  addLabelKey: 'freight.ui.addRoute',
  columns: routeColumns(false),
  rowDefaults: routePlaceRowDefaults,
}

/** Service Order Route tab: the same table plus actual date/time. */
export const SERVICE_ORDER_ROUTE_TABLE: FreightTable = {
  key: 'places',
  title: 'Route',
  titleKm: 'ផ្លូវ',
  addLabel: 'Add Route',
  addLabelKey: 'freight.ui.addRoute',
  columns: routeColumns(true),
  rowDefaults: routePlaceRowDefaults,
}
