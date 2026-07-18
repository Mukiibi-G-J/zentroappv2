import DynamicDocumentPage from '@/components/dynamic/DynamicDocumentPage'

interface Props {
  params: Promise<{ pageId: string; systemId: string }>
}

export default async function DocumentPage({ params }: Props) {
  const { pageId, systemId } = await params
  return <DynamicDocumentPage pageId={parseInt(pageId)} systemId={systemId} />
}
