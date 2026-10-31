/**
 * Cmd+K global search: keyword / semantic modes, Ask AI on demand, source links.
 */
import type { CommandPaletteItem, CommandPaletteGroup } from '@nuxt/ui'
import type { SearchHit, SearchMode } from '~/types/search'
import { useMenu } from '~/composables/layout/useMenu'
import { useSearch } from '~/composables/search/useSearch'

export function useGlobalSearch() {
  const { t } = useI18n()
  const { links, close: closeSidebar } = useMenu()
  const { askAi, searchKeyword, searchSemantic, cancelSearch, cancelAsk } = useSearch()

  const open = ref(false)
  const searchTerm = ref('')
  const mode = ref<SearchMode>('keyword')
  const loading = ref(false)
  const asking = ref(false)
  const hits = ref<SearchHit[]>([])
  const aiAnswer = ref<string | null>(null)
  const aiCitations = ref<SearchHit[]>([])
  let generation = 0
  let disposed = false
  let debounceTimer: ReturnType<typeof setTimeout> | null = null

  const isCurrent = (version: number) => !disposed && version === generation

  function invalidate() {
    generation++
    if (debounceTimer !== null) clearTimeout(debounceTimer)
    debounceTimer = null
    cancelSearch()
    cancelAsk()
    hits.value = []
    aiAnswer.value = null
    aiCitations.value = []
    loading.value = false
    asking.value = false
  }

  const navItems = computed<CommandPaletteItem[]>(() => {
    const items: CommandPaletteItem[] = []
    const navLinks = links.value?.[0] || []

    const pushLink = (label: string, to: string, icon?: string) => {
      items.push({
        id: `nav:${to}`,
        label,
        icon: icon || 'i-lucide-file',
        to,
        onSelect: () => {
          closeSidebar()
          open.value = false
        },
      })
    }

    for (const link of navLinks) {
      if (link.children?.length) {
        for (const child of link.children) {
          if (child.to) pushLink(String(child.label), String(child.to), child.icon || link.icon)
        }
      }
      else if (link.to) {
        pushLink(String(link.label), String(link.to), link.icon)
      }
    }

    // `useMenu` already applies the canonical permission keys.
    return items
  })

  async function runSearch(query: string, searchMode: SearchMode, version: number) {
    if (!isCurrent(version)) return
    loading.value = true
    try {
      const results = searchMode === 'semantic'
        ? await searchSemantic(query, { limit: 12 })
        : await searchKeyword(query, { limit: 12 })
      if (isCurrent(version)) hits.value = results
    }
    catch {
      if (isCurrent(version)) hits.value = []
    }
    finally {
      if (isCurrent(version)) loading.value = false
    }
  }

  watch([() => searchTerm.value.trim(), mode, open], ([query, searchMode, isOpen]) => {
    // Invalidate immediately, not 120 ms later: the previous response may arrive meanwhile.
    invalidate()
    if (!query || !isOpen || disposed) return
    const version = generation
    debounceTimer = setTimeout(() => {
      debounceTimer = null
      void runSearch(query, searchMode, version)
    }, 120)
  }, { flush: 'sync' })

  onScopeDispose(() => {
    disposed = true
    invalidate()
  })

  async function onAskAi() {
    const q = searchTerm.value.trim()
    if (!q || asking.value || !open.value || disposed) return
    const version = generation
    asking.value = true
    try {
      const res = await askAi(q, hits.value)
      if (!isCurrent(version)) return
      aiAnswer.value = res.answer
      aiCitations.value = res.citations
    }
    finally {
      if (isCurrent(version)) asking.value = false
    }
  }

  function setMode(next: SearchMode) {
    mode.value = next
  }

  const resultItems = computed<CommandPaletteItem[]>(() =>
    hits.value.map(hit => ({
      id: hit.id,
      label: hit.title,
      description: `${hit.sourceLabel} · ${hit.snippet}`,
      icon: hit.entityType === 'file' || hit.entityType === 'attachment'
        ? 'i-lucide-paperclip'
        : hit.entityType === 'meeting' || hit.entityType === 'meetingTopic'
          ? 'i-lucide-video'
          : 'i-lucide-file-text',
      to: hit.url,
      onSelect: () => {
        closeSidebar()
        open.value = false
      },
    })),
  )

  const askAiItems = computed<CommandPaletteItem[]>(() => {
    if (!searchTerm.value.trim()) return []
    return [{
      id: 'action:ask-ai',
      label: asking.value ? t('lcs.search.asking') : t('lcs.search.askAi'),
      description: t('lcs.search.askAiHint'),
      icon: 'i-lucide-sparkles',
      disabled: asking.value || loading.value,
      onSelect: async (e: Event) => {
        e.preventDefault()
        await onAskAi()
      },
    }]
  })

  const citationItems = computed<CommandPaletteItem[]>(() =>
    aiCitations.value.map(hit => ({
      id: `cite:${hit.id}`,
      label: hit.title,
      description: `${t('lcs.search.source')}: ${hit.sourceLabel} · ${hit.url}`,
      icon: 'i-lucide-link',
      to: hit.url,
      onSelect: () => {
        closeSidebar()
        open.value = false
      },
    })),
  )

  const groups = computed<CommandPaletteGroup<CommandPaletteItem>[]>(() => {
    const out: CommandPaletteGroup<CommandPaletteItem>[] = []

    if (askAiItems.value.length) {
      out.push({
        id: 'ask-ai',
        label: t('lcs.search.askAiGroup'),
        ignoreFilter: true,
        items: askAiItems.value,
      })
    }

    if (aiAnswer.value) {
      out.push({
        id: 'ai-answer',
        label: t('lcs.search.aiAnswer'),
        ignoreFilter: true,
        items: [{
          id: 'ai-answer-body',
          label: aiAnswer.value.split('\n')[0] || t('lcs.search.aiAnswer'),
          description: aiAnswer.value,
          icon: 'i-lucide-bot',
          disabled: true,
        }],
      })
      if (citationItems.value.length) {
        out.push({
          id: 'ai-sources',
          label: t('lcs.search.sources'),
          ignoreFilter: true,
          items: citationItems.value,
        })
      }
    }

    if (resultItems.value.length) {
      out.push({
        id: 'records-files',
        label: t('lcs.search.recordsAndFiles'),
        ignoreFilter: true,
        items: resultItems.value,
      })
    }

    out.push({
      id: 'navigation',
      label: t('common.pages'),
      items: navItems.value,
    })

    return out
  })

  const placeholder = computed(() =>
    mode.value === 'semantic'
      ? t('lcs.search.placeholderSemantic')
      : t('lcs.search.placeholderKeyword'),
  )

  return {
    open,
    searchTerm,
    mode,
    setMode,
    loading,
    asking,
    groups,
    placeholder,
    onAskAi,
  }
}
