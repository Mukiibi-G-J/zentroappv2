'use client'

import { useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Download, Eye, FileSpreadsheet, FileText, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { usePages } from '@/hooks/usePage'
import FinancialReportFormatModal from '@/components/dynamic/FinancialReportFormatModal'
import { pageService } from '@/services/page.service'
import {
  dateRangeForPeriodType,
  downloadBase64File,
  FINANCIAL_REPORT_PRINT_ACTION,
  isFinancialReportDownloadContent,
  openFinancialReportPdfPreview,
} from '@/lib/financialReport'
import { listDashboardPathByPageId } from '@/lib/pageRoutes'
import { extractApiErrorMessage } from '@/lib/apiError'
import type { RoleCentreReportAction, RoleCentreSection } from '@/types/page'
import type { PageActionResponse } from '@/types/page'

interface Props {
  section: RoleCentreSection
}

function isDownloadResponse(
  value: unknown,
): value is PageActionResponse & { Command: 'DOWNLOAD'; Content: unknown } {
  return (
    typeof value === 'object'
    && value !== null
    && 'Command' in value
    && (value as { Command?: string }).Command === 'DOWNLOAD'
  )
}

export default function ReportsSection({ section }: Props) {
  const router = useRouter()
  const { data: pages = [] } = usePages()
  const reports = section.Reports ?? []
  const [downloadTarget, setDownloadTarget] = useState<RoleCentreReportAction | null>(null)
  const [previewLoadingId, setPreviewLoadingId] = useState<string | null>(null)
  const [downloadLoading, setDownloadLoading] = useState(false)

  const listHref = useMemo(() => {
    if (!section.ListPageId) return null
    return listDashboardPathByPageId(pages, section.ListPageId)
  }, [pages, section.ListPageId])

  const runPreviewPdf = async (report: RoleCentreReportAction) => {
    if (!section.ListPageId) return
    const dates = dateRangeForPeriodType(report.PeriodType || 'Month')
    setPreviewLoadingId(report.SystemId)
    try {
      const result = await pageService.invokeAction(
        section.ListPageId,
        FINANCIAL_REPORT_PRINT_ACTION,
        report.SystemId,
        {
          BatchName: report.Name,
          Format: 'pdf',
          startDate: dates.startDate,
          endDate: dates.endDate,
        },
      )
      if (isDownloadResponse(result) && isFinancialReportDownloadContent(result.Content)) {
        openFinancialReportPdfPreview(result.Content.FileBase64, result.Content.MimeType)
        toast.success(`${report.Description} opened for preview`)
        return
      }
      toast.error('Preview returned no PDF content')
    } catch (err) {
      toast.error(extractApiErrorMessage(err) || 'Failed to preview report')
    } finally {
      setPreviewLoadingId(null)
    }
  }

  const runDownload = async (format: 'pdf' | 'excel') => {
    if (!downloadTarget || !section.ListPageId) return
    const dates = dateRangeForPeriodType(downloadTarget.PeriodType || 'Month')
    setDownloadLoading(true)
    try {
      const result = await pageService.invokeAction(
        section.ListPageId,
        FINANCIAL_REPORT_PRINT_ACTION,
        downloadTarget.SystemId,
        {
          BatchName: downloadTarget.Name,
          Format: format,
          startDate: dates.startDate,
          endDate: dates.endDate,
        },
      )
      if (isDownloadResponse(result) && isFinancialReportDownloadContent(result.Content)) {
        downloadBase64File(
          result.Content.FileBase64,
          result.Content.FileName,
          result.Content.MimeType,
        )
        toast.success(`${downloadTarget.Description} downloaded`)
        setDownloadTarget(null)
        return
      }
      toast.error('Download returned no file content')
    } catch (err) {
      toast.error(extractApiErrorMessage(err) || 'Failed to download report')
    } finally {
      setDownloadLoading(false)
    }
  }

  return (
    <div className="rounded-xl border border-strokeColor bg-white p-5">
      <div className="mb-4 flex items-center justify-between gap-3 border-b border-strokeColor pb-2">
        <h3 className="text-sm font-semibold text-mainTextColor">{section.Caption || 'Reports'}</h3>
        {listHref ? (
          <button
            type="button"
            onClick={() => router.push(listHref)}
            className="text-xs font-medium text-s1 hover:underline"
          >
            All financial reports
          </button>
        ) : null}
      </div>

      {reports.length === 0 ? (
        <p className="text-sm text-bodyText">
          No financial reports yet. Seed the income statement or create one under Finance.
        </p>
      ) : (
        <div className="space-y-2">
          {reports.map((report) => {
            const previewBusy = previewLoadingId === report.SystemId
            return (
              <div
                key={report.SystemId}
                className="flex flex-wrap items-center gap-2 rounded-lg border border-strokeColor/80 bg-softBg/40 px-3 py-2.5"
              >
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-mainTextColor truncate">
                    {report.Description}
                  </p>
                  <p className="text-xs text-bodyText">{report.Name}</p>
                </div>
                <div className="flex flex-wrap items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => void runPreviewPdf(report)}
                    disabled={previewBusy || downloadLoading}
                    className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium text-mainTextColor transition hover:bg-white disabled:opacity-50"
                    title="Preview PDF in browser"
                  >
                    {previewBusy ? <Loader2 size={14} className="animate-spin" /> : <Eye size={14} />}
                    Preview
                  </button>
                  <button
                    type="button"
                    onClick={() => setDownloadTarget(report)}
                    disabled={previewBusy || downloadLoading}
                    className="inline-flex items-center gap-1.5 rounded-md bg-s1 px-2.5 py-1.5 text-xs font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
                    title="Download PDF or Excel"
                  >
                    <Download size={14} />
                    Download
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}

      <div className="mt-3 flex flex-wrap gap-3 text-xs text-bodyText">
        <span className="inline-flex items-center gap-1">
          <FileText size={12} /> PDF
        </span>
        <span className="inline-flex items-center gap-1">
          <FileSpreadsheet size={12} /> Excel
        </span>
        {downloadLoading ? (
          <span className="inline-flex items-center gap-1 text-s1">
            <Loader2 size={12} className="animate-spin" /> Exporting…
          </span>
        ) : null}
      </div>

      <FinancialReportFormatModal
        open={downloadTarget != null}
        title="Download financial report"
        reportLabel={downloadTarget?.Description}
        loading={downloadLoading}
        onClose={() => {
          if (!downloadLoading) setDownloadTarget(null)
        }}
        onExportPdf={() => void runDownload('pdf')}
        onExportExcel={() => void runDownload('excel')}
      />
    </div>
  )
}
