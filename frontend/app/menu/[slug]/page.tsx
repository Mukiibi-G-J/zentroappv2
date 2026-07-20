import type { Metadata } from 'next'
import GuestDigitalMenu from '@/components/restaurant/GuestDigitalMenu'

export const metadata: Metadata = {
  title: 'Menu',
  description: 'View our menu',
}

export default async function MenuSlugPage({
  params,
}: {
  params: Promise<{ slug: string }>
}) {
  const { slug } = await params
  return <GuestDigitalMenu slug={slug || 'main'} />
}
