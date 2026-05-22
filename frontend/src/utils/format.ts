/**
 * Escape a value for safe insertion into HTML.
 * Ported from the vanilla JS `esc()` helper.
 */
export function esc(value: unknown): string {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/** Format a number with sign prefix: "+5" / "-3" / "0". */
export function withSign(n: number, decimals = 0): string {
  const s = n.toFixed(decimals);
  return n > 0 ? `+${s}` : s;
}

/** Pad a number to two digits: 7 -> "07". */
export function pad2(n: number): string {
  return String(n).padStart(2, '0');
}

/** Round to one decimal place. */
export function round1(n: number): number {
  return Math.round(n * 10) / 10;
}

/** Format a percentage from a 0-1 fraction: 0.652 -> "65%". */
export function pct(fraction: number): string {
  return `${Math.round(fraction * 100)}%`;
}
