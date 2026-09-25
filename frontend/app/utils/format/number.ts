/** Coerce any value to a finite number; NaN/Infinity fall back to `fallback`. */
export function toFiniteNumber(value: unknown, fallback = 0): number {
  const n = Number(value ?? 0)
  return Number.isFinite(n) ? n : fallback
}
