import { describe, expect, it } from 'vitest'
import { snapshotPreviewTabs } from '../app/utils/freight/config-version-preview'
import type { ConfigurationVersion } from '../app/types/component-config'

describe('configuration version preview', () => {
  it('maps the stored snapshot field names onto the runtime renderer shape', () => {
    const version = {
      id: '3',
      versionNo: 3,
      status: 'RETIRED',
      tabCount: 1,
      configSnapshot: {
        tabs: [{
          id: 'tab-1',
          code: 'CUSTOMS',
          name: 'Customs',
          tradeDirectionId: '1',
          displayOrder: 10,
          groups: [{
            id: 'group-1',
            tabGroupId: 'link-1',
            code: 'customs',
            name: 'Customs',
            renderMode: 'table',
            displayOrder: 5,
            displayMode: 'table_only',
            dataCardinality: 'multiple',
            formColumns: 3,
            editable: true,
            attributes: [{
              id: 'attr-1',
              code: 'declaration_no',
              label: 'Declaration No.',
              dataType: 'text',
              isRequired: true,
              isVisible: true,
              displayOrder: 20,
            }],
          }],
        }],
      },
    } as ConfigurationVersion

    const [tab] = snapshotPreviewTabs(version)
    expect(tab.tradeDirectionId).toBe('1')
    expect(tab.name).toBe('Customs')

    const [group] = tab.groups
    expect(group.tabGroupId).toBe('link-1')
    expect(group.displayMode).toBe('table_only')
    expect(group.dataCardinality).toBe('multiple')

    const [attribute] = group.attributes
    expect(attribute.fieldType).toBe('text')
    expect(attribute.sortOrder).toBe(20)
    expect(attribute.isRequired).toBe(true)
  })

  it('falls back to the legacy render mode for snapshots written before layouts existed', () => {
    const version = {
      id: '1',
      versionNo: 1,
      status: 'RETIRED',
      tabCount: 1,
      configSnapshot: {
        tabs: [{
          id: 'tab-1',
          code: 'GENERAL',
          name: 'General',
          groups: [{ id: 'g1', code: 'g', name: 'G', renderMode: 'form', attributes: [] }],
        }],
      },
    } as ConfigurationVersion

    expect(snapshotPreviewTabs(version)[0]!.groups[0]).toMatchObject({
      displayMode: 'form_only',
      dataCardinality: 'single',
      formColumns: 3,
    })
  })

  it('returns an empty list for a version without a snapshot', () => {
    expect(snapshotPreviewTabs(null)).toEqual([])
    expect(snapshotPreviewTabs({ id: '1', versionNo: 1, status: 'DRAFT', tabCount: 0 } as ConfigurationVersion)).toEqual([])
  })
})
