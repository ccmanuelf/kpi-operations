import type { Page } from '@playwright/test'
import type { Sample } from '../../src/utils/contrastAudit'

// Reads computed colors + geometry for every visible text element on the current
// page. Pure DOM extraction — all contrast math happens in Node (contrastAudit).
export async function collectSamples(
  page: Page,
  screen: string,
  theme: 'light' | 'dark',
): Promise<Sample[]> {
  const raw = await page.evaluate(() => {
    const out: Array<Omit<Sample, 'screen' | 'theme'>> = []
    for (const el of Array.from(document.querySelectorAll('body *'))) {
      const own = Array.from(el.childNodes)
        .filter((n) => n.nodeType === 3)
        .map((n) => (n.textContent || '').trim())
        .join('')
        .trim()
      if (!own) continue
      const cs = getComputedStyle(el)
      if (cs.visibility === 'hidden' || cs.display === 'none' || +cs.opacity === 0) continue
      const r = el.getBoundingClientRect()
      if (r.width < 1 || r.height < 1) continue
      if (r.bottom < 0 || r.top > window.innerHeight || r.right < 0 || r.left > window.innerWidth) continue
      const bgStack: string[] = []
      const gradientStops: string[] = []
      let node: Element | null = el
      while (node) {
        const ncs = getComputedStyle(node)
        if (ncs.backgroundColor) bgStack.push(ncs.backgroundColor)
        const bi = ncs.backgroundImage
        if (bi && bi.includes('gradient')) {
          const ms = bi.match(/rgba?\([^)]*\)|#[0-9a-fA-F]{3,8}/g) || []
          gradientStops.push(...ms)
        }
        node = node.parentElement
      }
      out.push({
        text: own.slice(0, 60),
        cls: el.className?.toString?.() || '',
        color: cs.color,
        fontSize: parseFloat(cs.fontSize) || 0,
        fontWeight: parseInt(cs.fontWeight) || 400,
        bgStack,
        gradientStops,
      })
    }
    return out
  })
  return raw.map((s) => ({ ...s, screen, theme }))
}
