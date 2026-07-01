import { useState, useEffect, useCallback } from 'react'
import { api } from '@/api/client'
import type { GroupInfo } from '@/types'

// Module-level singleton cache — survives page navigation within the SPA session.
let _groups: GroupInfo[] | null = null
let _pending: Promise<GroupInfo[]> | null = null

export function useCachedGroups() {
  // Seed state from the module cache so the first render already has data
  const [groups, setGroups] = useState<GroupInfo[]>(_groups ?? [])
  const [loading, setLoading] = useState(!_groups)

  useEffect(() => {
    // Already cached — nothing to do
    if (_groups) return

    // Deduplicate concurrent calls — reuse the in-flight promise
    if (!_pending) {
      _pending = api
        .getGroups()
        .then((r) => r.groups ?? [])
        .then((list) => {
          _groups = list
          return list
        })
        .finally(() => {
          _pending = null
        })
    }

    let cancelled = false
    _pending.then((list) => {
      if (!cancelled) {
        setGroups(list)
        setLoading(false)
      }
    })

    return () => {
      cancelled = true
    }
  }, [])

  const refresh = useCallback(() => {
    _groups = null
    setLoading(true)
    api
      .getGroups()
      .then((r) => {
        _groups = r.groups ?? []
        setGroups(_groups)
      })
      .finally(() => setLoading(false))
  }, [])

  return { groups, loading, refresh } as const
}
