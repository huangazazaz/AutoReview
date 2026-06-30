/**
 * Format a decimal as a percentage string (e.g., 0.1523 → "+15.23%").
 * Returns signed percentage with 2 decimal places.
 */
export function formatPct(value: number | null | undefined): string {
  if (value == null || isNaN(value)) return '—'
  const pct = value * 100
  const sign = pct >= 0 ? '+' : ''
  return `${sign}${pct.toFixed(2)}%`
}

/**
 * Format a number to a fixed number of decimal places.
 */
export function formatNumber(value: number | null | undefined, decimals = 2): string {
  if (value == null || isNaN(value)) return '—'
  return value.toFixed(decimals)
}

/**
 * Format a number as a currency amount with thousand separators.
 */
export function formatAmount(value: number | null | undefined): string {
  if (value == null || isNaN(value)) return '—'
  return value.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
