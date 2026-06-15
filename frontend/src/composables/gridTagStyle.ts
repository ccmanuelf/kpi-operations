// Shared inline style for compact, spreadsheet-natural status/priority tags in
// AG Grid HTML cell renderers. Square (radius 3px, not a pill) and tighter than
// the old chip so it sits cleanly in the 38px compact rows. White text on the
// caller's solid color — callers pass AA-safe colors (see PR1 a11y work).
export const tagStyle = (background: string): string => `
    display: inline-block;
    padding: 1px 6px;
    border-radius: 3px;
    font-size: 11px;
    font-weight: 600;
    line-height: 1.4;
    color: #ffffff;
    background: ${background};
  `
