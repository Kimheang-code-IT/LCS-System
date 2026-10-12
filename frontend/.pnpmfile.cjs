/**
 * pnpm readPackage hook (see https://pnpm.io/pnpmfile).
 *
 * The LCS frontend does not use rich-text editing. `@nuxt/ui` ships Tiptap
 * (`@tiptap/*`, plus the `prosemirror-*` tree it pulls in) as direct
 * dependencies for its Editor components, which forces those packages into
 * every install and into `pnpm-lock.yaml`.
 *
 * This hook strips the Tiptap entries from the `@nuxt/ui` manifest before pnpm
 * resolves it, so no Tiptap package is resolved, downloaded, or linked.
 * Nothing in the application imports them — no `UEditor*` component is used.
 *
 * IMPORTANT: if the project ever adopts Nuxt UI's editor components
 * (`UEditor`, `UEditorToolbar`, `UEditorDragHandle`, ...), delete this file
 * and run `pnpm install --no-frozen-lockfile` to restore the Tiptap
 * dependencies. Frozen installs fail while the lockfile and this file
 * disagree (`pnpmfileChecksum`), by design.
 */
module.exports = {
  hooks: {
    readPackage(pkg) {
      if (pkg.name !== '@nuxt/ui') {
        return pkg
      }

      for (const field of ['dependencies', 'optionalDependencies', 'peerDependencies']) {
        for (const name of Object.keys(pkg[field] ?? {})) {
          if (name.startsWith('@tiptap/')) {
            delete pkg[field][name]
          }
        }
      }
      for (const name of Object.keys(pkg.peerDependenciesMeta ?? {})) {
        if (name.startsWith('@tiptap/')) {
          delete pkg.peerDependenciesMeta[name]
        }
      }

      return pkg
    },
  },
}
