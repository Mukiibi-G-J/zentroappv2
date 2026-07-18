import * as LucideIcons from 'lucide-react'
import { BookOpen, type LucideIcon } from 'lucide-react'

/** True when ImageUrl points at a remote or static asset (not a Lucide icon name). */
export function isRibbonImageUrl(imageUrl: string): boolean {
  return (
    imageUrl.startsWith('http://')
    || imageUrl.startsWith('https://')
    || imageUrl.startsWith('/')
  )
}

/** Resolve PageAction.ImageUrl to a Lucide component (PascalCase name from seed/DB). */
export function resolveRibbonIcon(imageUrl?: string | null): LucideIcon {
  const name = imageUrl?.trim()
  if (!name || isRibbonImageUrl(name)) return BookOpen
  const icon = (LucideIcons as unknown as Record<string, LucideIcon | undefined>)[name]
  return icon ?? BookOpen
}
