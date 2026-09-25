/** Lowercase kebab slug used for i18n keys, DOM anchors and download filenames. */
export function slugify(value: string, fallback = 'general'): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || fallback
}
