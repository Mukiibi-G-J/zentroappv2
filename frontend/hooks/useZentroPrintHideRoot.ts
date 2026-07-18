'use client'

import { useEffect } from 'react'
import { ZENTRO_PRINT_HIDE_APP_ROOT_CLASS } from '@/lib/zentroPrintClassNames'

/**
 * Adds a class on `<html>` around `beforeprint` / `afterprint` while the owning UI is open.
 * Use together with CSS that hides the app shell during print; printable content must be portaled.
 */
export function useZentroPrintHideRootWhileOpen(isActive: boolean) {
  useEffect(() => {
    if (!isActive) return
    const cls = ZENTRO_PRINT_HIDE_APP_ROOT_CLASS
    const onBeforePrint = () => document.documentElement.classList.add(cls)
    const onAfterPrint = () => document.documentElement.classList.remove(cls)
    window.addEventListener('beforeprint', onBeforePrint)
    window.addEventListener('afterprint', onAfterPrint)
    return () => {
      window.removeEventListener('beforeprint', onBeforePrint)
      window.removeEventListener('afterprint', onAfterPrint)
      document.documentElement.classList.remove(cls)
    }
  }, [isActive])
}

export function ensureZentroPrintHideRootBeforePrint() {
  document.documentElement.classList.add(ZENTRO_PRINT_HIDE_APP_ROOT_CLASS)
}
