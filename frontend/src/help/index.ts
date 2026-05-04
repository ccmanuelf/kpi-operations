/**
 * Help Center module — loads and exposes user-guide markdown files.
 *
 * Files live at `docs/user-guide/*.md` (project root) so they remain
 * the single source of truth for both the Markdown viewer here and any
 * external doc tooling. Vite's `?raw` query yields the file contents
 * as a string at build time; the `eager: true` flag inlines them
 * synchronously so the Help Center boots without an extra round trip.
 */

// Lazy import for raw markdown text. Filenames carry the section
// ordering (01-, 02-, …) so sorting by key gives the user-facing order.
const modules = import.meta.glob('../../../docs/user-guide/*.md', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>

export interface HelpDoc {
  /** Slug-style id used in routes/links (e.g. `01-getting-started`). */
  id: string
  /** Filename (e.g. `01-getting-started.md`). */
  filename: string
  /** Section number prefix (e.g. `01`) — null for README and glossary. */
  order: string | null
  /** Display title (extracted from the first H1 in the file). */
  title: string
  /** Raw markdown body (post-H1, ready for the renderer). */
  body: string
  /** Full raw markdown including the H1 — useful for "view source". */
  raw: string
}

/**
 * Extract the H1 title from a markdown blob and return both the title
 * and the body without the H1 line. Falls back to the slug if no H1.
 */
function splitTitle(raw: string, fallback: string): { title: string; body: string } {
  const lines = raw.split('\n')
  const h1Idx = lines.findIndex((l) => /^#\s+/.test(l))
  if (h1Idx === -1) {
    return { title: fallback, body: raw }
  }
  const title = lines[h1Idx].replace(/^#\s+/, '').trim()
  const body = lines.slice(h1Idx + 1).join('\n').trim()
  return { title, body }
}

function buildDoc(path: string, raw: string): HelpDoc {
  const filename = path.split('/').pop() || ''
  const id = filename.replace(/\.md$/, '')
  const orderMatch = id.match(/^(\d+)/)
  const order = orderMatch ? orderMatch[1] : null
  const { title, body } = splitTitle(raw, id)
  return { id, filename, order, title, body, raw }
}

const docs: HelpDoc[] = Object.entries(modules)
  .map(([path, raw]) => buildDoc(path, raw))
  .sort((a, b) => {
    // README first, then numbered sections, then glossary last.
    if (a.id === 'README') return -1
    if (b.id === 'README') return 1
    if (a.id === 'glossary') return 1
    if (b.id === 'glossary') return -1
    if (a.order && b.order) return a.order.localeCompare(b.order)
    return a.id.localeCompare(b.id)
  })

export function getAllDocs(): HelpDoc[] {
  return docs
}

export function getDocById(id: string): HelpDoc | undefined {
  return docs.find((d) => d.id === id)
}

export function getDefaultDocId(): string {
  return 'README'
}
