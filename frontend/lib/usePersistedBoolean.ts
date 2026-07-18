'use client'

import { useCallback, useState } from 'react'

export function usePersistedBoolean(storageKey: string, defaultValue: boolean) {
  const [value, setValue] = useState(() => {
    if (typeof window === 'undefined') return defaultValue
    const stored = window.localStorage.getItem(storageKey)
    return stored !== null ? stored === 'true' : defaultValue
  })

  const setPersisted = useCallback(
    (next: boolean | ((prev: boolean) => boolean)) => {
      setValue((prev) => {
        const resolved = typeof next === 'function' ? next(prev) : next
        window.localStorage.setItem(storageKey, String(resolved))
        return resolved
      })
    },
    [storageKey],
  )

  return [value, setPersisted] as const
}
