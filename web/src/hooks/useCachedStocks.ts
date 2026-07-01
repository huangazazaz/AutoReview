import { useState, useEffect, useCallback } from 'react'
import { api } from '@/api/client'
import type { CachedStock } from '@/types'

// Module-level singleton cache — survives page navigation within the SPA session.
let _stocks: CachedStock[] | null = null
let _pending: Promise<CachedStock[]> | null = null

export function useCachedStocks() {
  // Seed state from the module cache so the first render already has data
  const [stocks, setStocks] = useState<CachedStock[]>(_stocks ?? [])
  const [loading, setLoading] = useState(!_stocks)

  useEffect(() => {
    // Already cached — nothing to do
    if (_stocks) return

    // Deduplicate concurrent calls — reuse the in-flight promise
    if (!_pending) {
      _pending = api
        .getCachedStocks()
        .then((r) => r.symbols ?? [])
        .then((list) => {
          _stocks = list
          return list
        })
        .finally(() => {
          _pending = null
        })
    }

    let cancelled = false
    _pending.then((list) => {
      if (!cancelled) {
        setStocks(list)
        setLoading(false)
      }
    })

    return () => {
      cancelled = true
    }
  }, [])

  const refresh = useCallback(() => {
    _stocks = null
    setLoading(true)
    api
      .getCachedStocks()
      .then((r) => {
        _stocks = r.symbols ?? []
        setStocks(_stocks)
      })
      .finally(() => setLoading(false))
  }, [])

  return { stocks, loading, refresh } as const
}
