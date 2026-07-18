import RecordPageRouter from '@/components/dynamic/RecordPageRouter'

interface Props {
  params: Promise<{ pageId: string; systemId: string }>
}

export default async function DetailPage({ params }: Props) {
  const { pageId, systemId } = await params
  return <RecordPageRouter pageId={parseInt(pageId)} systemId={systemId} />
}
