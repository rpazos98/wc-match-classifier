// ── Classification label constants ────────────────────────────────────────────

export const LBL_IMP  = 'Imperdible';
export const LBL_VALE = 'Vale la pena';
export const LBL_RES  = 'Para ver el resumen';

// ── CSS-class helpers ─────────────────────────────────────────────────────────

/** Row highlight class by classification label. */
export function rowClass(label: string): string {
  if (label === LBL_IMP)  return 'r-imp';
  if (label === LBL_VALE) return 'r-vale';
  return 'r-res';
}

/** Section header class by classification label. */
export function hdrClass(label: string): string {
  if (label === LBL_IMP)  return 'hdr-imp';
  if (label === LBL_VALE) return 'hdr-vale';
  return 'hdr-res';
}

// ── Color helpers ─────────────────────────────────────────────────────────────

/** Score text colour (red / orange / green) by numeric score 0-100. */
export function scoreColor(score: number): string {
  if (score >= 60) return '#e83333';
  if (score >= 30) return '#e89515';
  return '#4a6035';
}

/** Progress-bar colour by a 0-1 fraction (green / orange / dark-green). */
export function barColor(pct: number): string {
  if (pct >= 0.7) return '#5ed64a';
  if (pct >= 0.4) return '#e89515';
  return '#3a5030';
}
