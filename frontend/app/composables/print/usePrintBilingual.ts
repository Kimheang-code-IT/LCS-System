export function usePrintBilingual() {
  const { t, loadLocaleMessages } = useI18n()
  const khmerReady = ref(false)

  onMounted(async () => {
    await Promise.all([loadLocaleMessages('km'), loadLocaleMessages('en')])
    khmerReady.value = true
  })

  function kmText(key: string): string {
    void khmerReady.value
    try {
      const text = t(key, {}, { locale: 'km' })
      return text === key ? '' : text
    }
    catch {
      return ''
    }
  }

  function bi(key: string): string {
    const khmerLine = kmText(key)
    const english = t(key, {}, { locale: 'en' })
    return khmerLine ? `${khmerLine}\n${english}` : english
  }

  function biInline(key: string): string {
    const khmerLine = kmText(key)
    const english = t(key, {}, { locale: 'en' })
    return khmerLine ? `${khmerLine} / ${english}` : english
  }

  function khmer(key: string): string {
    return kmText(key)
  }

  return { khmerReady, bi, biInline, khmer }
}
