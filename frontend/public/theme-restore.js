// Pre-hydration dark-theme restore. Externalized (rather than inline) so it
// satisfies the CSP `script-src 'self'` directive without a script-hash
// allowlist entry — see frontend/nginx.conf. Kept as a classic, blocking
// <script src> (no type="module"/async/defer) in <head> so it still runs
// synchronously before <body> paints, same timing as the inline version it
// replaced.
try {
  var t = localStorage.getItem('kpi-theme')
  if (t) {
    var d = JSON.parse(t).isDark
    if (d) document.documentElement.setAttribute('data-theme', 'dark')
  }
} catch {
  // best-effort — localStorage unavailable or malformed; fall back to light theme
}
