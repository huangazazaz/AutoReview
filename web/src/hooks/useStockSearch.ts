import { useState, useEffect, useMemo, useRef } from 'react'
import type { CachedStock } from '@/types'

interface StockOption {
  value: string
  label: string
}

/** Debounced stock search — filters cached stocks after 500ms of inactivity. */
export function useStockSearch(cachedStocks: CachedStock[]) {
  const [input, setInput] = useState('')
  const [debounced, setDebounced] = useState('')
  const timerRef = useRef<ReturnType<typeof setTimeout>>()

  // Debounce 500ms
  useEffect(() => {
    clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => setDebounced(input), 500)
    return () => clearTimeout(timerRef.current)
  }, [input])

  // Filter on debounced value, cap at 100 results
  const options = useMemo<StockOption[]>(() => {
    if (!debounced.trim()) return []
    const q = debounced.toLowerCase()
    const matches: StockOption[] = []
    for (const s of cachedStocks) {
      if (s.symbol.toLowerCase().includes(q) || s.name.toLowerCase().includes(q)) {
        matches.push({
          value: s.symbol,
          label: `${s.symbol}${s.name ? ` - ${s.name}` : ''}`,
        })
        if (matches.length >= 100) break
      }
    }
    return matches
  }, [cachedStocks, debounced])

  // Find display label for a selected symbol
  const getLabel = (symbol: string) => {
    const s = cachedStocks.find(cs => cs.symbol === symbol)
    return s ? `${symbol} - ${s.name}` : symbol
  }

  return { input, setInput, options, getLabel }
}
