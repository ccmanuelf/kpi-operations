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
      // Each gradient is tagged with the depth of the node carrying it, so the
      // contrast math can composite its stops over the surface beneath THAT
      // node. Without the depth a stop is just a colour with nowhere to sit,
      // and a translucent one gets mistaken for an opaque background.
      const gradients: Array<{ depth: number; stops: string[] }> = []
      let node: Element | null = el
      let depth = 0
      while (node) {
        const ncs = getComputedStyle(node)
        // Push unconditionally: bgStack indexes MUST line up with `depth`.
        // Skipping a node here would silently shift every deeper gradient
        // onto the wrong surface.
        bgStack.push(ncs.backgroundColor)
        const bi = ncs.backgroundImage
        if (bi && bi.includes('gradient')) {
          // `color()` is matched as well as rgb/hex because parseColor
          // understands the srgb form and computed styles can serialise wide-
          // gamut colours that way. A stop in a syntax parseColor cannot read
          // (oklch, oklab) yields null, gets filtered, and the walk falls
          // through to the background-color rather than scoring a wrong value.
          const stops =
            bi.match(/rgba?\([^)]*\)|color\([^)]*\)|#[0-9a-fA-F]{3,8}/g) || []
          if (stops.length) gradients.push({ depth, stops })
        }
        node = node.parentElement
        depth++
      }
      out.push({
        text: own.slice(0, 60),
        cls: el.className?.toString?.() || '',
        color: cs.color,
        fontSize: parseFloat(cs.fontSize) || 0,
        fontWeight: parseInt(cs.fontWeight) || 400,
        bgStack,
        gradients,
      })
    }
    return out
  })
  return raw.map((s) => ({ ...s, screen, theme }))
}
