/** Latest date available in cached stock data. */
export const MAX_DATE = '2026-06-18'

/** react-select filterOption: fast prefix/substring match, capped at 100 results. */
export function filterStockOption(
  { label, value, data }: { label: string; value: string; data: any },
  input: string
): boolean {
  if (!input) return true  // show all when empty (but defaultOptions handles this)
  const q = input.toLowerCase()
  return value.toLowerCase().includes(q) || label.toLowerCase().includes(q)
}

/** Cap visible options to avoid rendering thousands of items. */
export const MAX_VISIBLE_OPTIONS = 200
