import { resolveMediaUrl } from '@/lib/media'

const AVATAR_STYLES = [
  'avataaars',
  'lorelei',
  'notionists',
  'fun-emoji',
  'adventurer',
  'pixel-art',
] as const

function hashString(value: string): number {
  let hash = 0
  for (let i = 0; i < value.length; i += 1) {
    hash = (hash << 5) - hash + value.charCodeAt(i)
    hash |= 0
  }
  return Math.abs(hash)
}

/** Deterministic generated avatar (varied style per user). */
export function getGeneratedAvatarUrl(seed: string, size = 128): string {
  const normalized = seed.trim() || 'user'
  const style = AVATAR_STYLES[hashString(normalized) % AVATAR_STYLES.length]
  const params = new URLSearchParams({
    seed: normalized,
    size: String(size),
  })
  return `https://api.dicebear.com/7.x/${style}/png?${params.toString()}`
}

/** Use uploaded avatar when present; otherwise a generated placeholder. */
export function resolveProfileAvatarSrc(
  avatar?: string | null,
  seed?: string | null,
  size = 128,
): string {
  const uploaded = avatar?.trim()
  if (uploaded) {
    return resolveMediaUrl(uploaded) ?? getGeneratedAvatarUrl(seed?.trim() || 'user', size)
  }
  return getGeneratedAvatarUrl(seed?.trim() || 'user', size)
}
