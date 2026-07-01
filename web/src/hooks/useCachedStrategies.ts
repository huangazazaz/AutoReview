import { useState, useEffect, useCallback } from 'react'
import { api } from '@/api/client'
import type { StrategyInfo } from '@/types'

// Module-level singleton cache — survives page navigation within the SPA session.
let _strategies: StrategyInfo[] | null = null
let _pending: Promise<StrategyInfo[]> | null = null

export function useCachedStrategies() {
  // Seed state from the module cache so the first render already has data
  const [strategies, setStrategies] = useState<StrategyInfo[]>(_strategies ?? [])
  const [loading, setLoading] = useState(!_strategies)

  useEffect(() => {
    // Already cached — nothing to do
    if (_strategies) return

    // Deduplicate concurrent calls — reuse the in-flight promise
    if (!_pending) {
      _pending = api
        .getStrategies()
        .then((r) => r.strategies ?? [])
        .then((list) => {
          _strategies = list
          return list
        })
        .finally(() => {
          _pending = null
        })
    }

    let cancelled = false
    _pending.then((list) => {
      if (!cancelled) {
        setStrategies(list)
        setLoading(false)
      }
    })

    return () => {
      cancelled = true
    }
  }, [])

  const refresh = useCallback(() => {
    _strategies = null
    setLoading(true)
    api
      .getStrategies()
      .then((r) => {
        _strategies = r.strategies ?? []
        setStrategies(_strategies)
      })
      .finally(() => setLoading(false))
  }, [])

  return { strategies, loading, refresh } as const
}
