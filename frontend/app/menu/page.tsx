import type { Metadata } from 'next'
import GuestDigitalMenu from '@/components/restaurant/GuestDigitalMenu'

export const metadata: Metadata = {
  title: 'Menu',
  description: 'View our menu',
}

export default function MenuPage() {
  return <GuestDigitalMenu slug="main" />
}
