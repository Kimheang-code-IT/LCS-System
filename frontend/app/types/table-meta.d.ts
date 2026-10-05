import type { RowData } from '@tanstack/vue-table'

/**
 * `@nuxt/ui` declares `ColumnMeta` on `@tanstack/table-core`, which pnpm does not
 * expose as a direct dependency here, so augmenting that specifier silently
 * creates a new module instead of merging. `@tanstack/vue-table` re-exports it
 * and *is* resolvable, so that is the augmentation target.
 */
declare module '@tanstack/vue-table' {
  interface ColumnMeta<_TData extends RowData, _TValue> {
    /**
     * Toolbar sort-menu hint: picks the direction labels for this column
     * (date → old/new, number → small/large, text → A→Z). When omitted the
     * kind is inferred from the column key.
     */
    sortKind?: 'date' | 'number' | 'text'
  }
}

export {}