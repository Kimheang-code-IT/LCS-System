import fs from 'node:fs'
import path from 'node:path'

const root = path.resolve('D:/project/Freight Forwarding/frontend')
const src = [
  'app/config/freight-modules.ts',
  'app/config/lcs-reference-modules.ts',
].map(f => fs.readFileSync(path.join(root, f), 'utf8')).join('\n')

function slug(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '') || 'general'
}

function take(str, re) {
  const m = str.match(re)
  return m ? m[1] : ''
}

const fields = {}
const sections = {}
const modules = {}
const tables = {}
const actions = {}

function addField(key, en, km) {
  if (!key || !en) return
  if (!fields[key]) fields[key] = { en, km: km || en }
}

function addSection(en, km) {
  if (!en) return
  const id = slug(en)
  if (!sections[id]) sections[id] = { en, km: km || en }
}

for (const fn of ['f', 'field', 'col', 'column']) {
  const re = new RegExp(`\\b${fn}\\(\\s*'([^']+)'\\s*,\\s*'((?:\\\\'|[^'])*)'\\s*,\\s*'((?:\\\\'|[^'])*)'(?:\\s*,\\s*'((?:\\\\'|[^'])*)'\\s*,\\s*'((?:\\\\'|[^'])*)')?`, 'g')
  for (const m of src.matchAll(re)) {
    addField(m[1], m[2], m[3])
    addSection(m[4], m[5])
  }
}

for (const m of src.matchAll(/key:\s*'([^']+)'[\s\S]{0,180}?label:\s*'((?:\\'|[^'])*)'[\s\S]{0,80}?labelKm:\s*'((?:\\'|[^'])*)'/g)) {
  addField(m[1], m[2], m[3])
}

const blocks = src.split(/createModule\(|\bmodule\(/).slice(1)
for (const block of blocks) {
  const collection = take(block, /collection:\s*'([^']+)'/)
  const title = take(block, /title:\s*'((?:\\'|[^'])*)'/)
  const titleKm = take(block, /titleKm:\s*'((?:\\'|[^'])*)'/)
  const singular = take(block, /singular:\s*'((?:\\'|[^'])*)'/)
  const singularKm = take(block, /singularKm:\s*'((?:\\'|[^'])*)'/)
  const description = take(block, /description:\s*'((?:\\'|[^'])*)'/)
  const descriptionKm = take(block, /descriptionKm:\s*'((?:\\'|[^'])*)'/)
  if (collection && title) {
    modules[collection] = {
      title: { en: title, km: titleKm || title },
      singular: { en: singular || title, km: singularKm || titleKm || title },
      description: { en: description, km: descriptionKm || description },
    }
  }
}

for (const m of src.matchAll(/key:\s*'([^']+)'\s*,\s*title:\s*'((?:\\'|[^'])*)'\s*,\s*titleKm:\s*'((?:\\'|[^'])*)'/g)) {
  tables[m[1]] = { en: m[2], km: m[3] }
}

for (const m of src.matchAll(/key:\s*'([^']+)'\s*,\s*label:\s*'((?:\\'|[^'])*)'\s*,\s*labelKm:\s*'((?:\\'|[^'])*)'\s*,\s*icon:/g)) {
  actions[m[1]] = { en: m[2], km: m[3] }
}

function localeMap(pairs, pick) {
  return Object.fromEntries(
    Object.entries(pairs)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([key, value]) => [key, pick(value)]),
  )
}

function nestModules(pick) {
  return Object.fromEntries(
    Object.entries(modules)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([key, value]) => [key, {
        title: pick(value.title),
        singular: pick(value.singular),
        description: pick(value.description),
      }]),
  )
}

const enFreightExtra = {
  fields: localeMap(fields, v => v.en),
  sections: localeMap(sections, v => v.en),
  modules: nestModules(v => v.en),
  tables: localeMap(tables, v => v.en),
  moduleActions: localeMap(actions, v => v.en),
}

const kmFreightExtra = {
  fields: localeMap(fields, v => v.km),
  sections: localeMap(sections, v => v.km),
  modules: nestModules(v => v.km),
  tables: localeMap(tables, v => v.km),
  moduleActions: localeMap(actions, v => v.km),
}

fs.writeFileSync(path.join(root, 'scripts/freight-i18n-extract.json'), JSON.stringify({ en: enFreightExtra, km: kmFreightExtra }, null, 2))
console.log(JSON.stringify({
  fields: Object.keys(fields).length,
  sections: Object.keys(sections).length,
  modules: Object.keys(modules).length,
  tables: Object.keys(tables).length,
  actions: Object.keys(actions).length,
}, null, 2))
