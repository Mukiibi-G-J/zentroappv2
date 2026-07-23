import type { Metadata } from 'next'
import { NotFoundPage } from '@/components/NotFoundPage'

export const metadata: Metadata = {
  title: 'Page not found — ZentroApp',
  description: 'This page could not be found. Find your workspace or return home.',
}

export default function NotFound() {
  return <NotFoundPage />
}
