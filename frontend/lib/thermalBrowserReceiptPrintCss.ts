import {
  ZENTRO_PRINT_HIDE_APP_ROOT_CLASS,
  ZENTRO_THERMAL_PRINT_CHROME_CLASS,
  ZENTRO_THERMAL_PRINT_DIALOG_CLASS,
  ZENTRO_THERMAL_PRINT_OVERLAY_CLASS,
} from './zentroPrintClassNames'

/**
 * Browser print stylesheet for narrow thermal receipts (~48mm).
 * Pair with portal + html.{ZENTRO_PRINT_HIDE_APP_ROOT_CLASS} (app shell hidden).
 */
export const THERMAL_BROWSER_RECEIPT_PRINT_CSS = `
  @page {
    margin: 0;
  }
  @media print {
    * {
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }
    html, body {
      margin: 0 !important;
      padding: 0 !important;
      height: auto !important;
      min-height: 0 !important;
      overflow: visible !important;
      background: white !important;
    }
    html.${ZENTRO_PRINT_HIDE_APP_ROOT_CLASS} body > *:not(.${ZENTRO_THERMAL_PRINT_OVERLAY_CLASS}) {
      display: none !important;
    }
    .${ZENTRO_THERMAL_PRINT_OVERLAY_CLASS} {
      position: static !important;
      inset: auto !important;
      display: block !important;
      padding: 0 !important;
      margin: 0 !important;
      height: auto !important;
      max-height: none !important;
      overflow: visible !important;
      background: white !important;
      z-index: auto !important;
    }
    .${ZENTRO_THERMAL_PRINT_DIALOG_CLASS} {
      max-height: none !important;
      overflow: visible !important;
      box-shadow: none !important;
      border-radius: 0 !important;
      width: 48mm !important;
      max-width: 48mm !important;
      margin: 0 !important;
      box-sizing: border-box !important;
    }
    .${ZENTRO_THERMAL_PRINT_CHROME_CLASS} {
      display: none !important;
    }
    .receipt-container {
      position: relative !important;
      left: auto !important;
      top: auto !important;
      width: 48mm !important;
      max-width: 48mm !important;
      min-width: 0 !important;
      margin: 0 !important;
      padding: 0.25mm 0.75mm !important;
      box-sizing: border-box !important;
      overflow: visible !important;
      break-inside: avoid;
      page-break-inside: avoid;
    }
    .receipt-container .receipt-print-title {
      font-size: 12px !important;
      line-height: 1.15 !important;
      letter-spacing: -0.04em !important;
    }
    .receipt-container .summary-section {
      box-sizing: border-box !important;
      padding: 0 !important;
      margin: 0 !important;
    }
    .receipt-container .summary-section .grid {
      display: grid !important;
      grid-template-columns: minmax(0, 1fr) min-content !important;
      gap: 1px 2px !important;
      align-items: baseline !important;
      width: 100% !important;
      box-sizing: border-box !important;
    }
    .receipt-container .summary-section .grid > span:first-child {
      font-size: 8px !important;
      line-height: 1.2 !important;
      padding-right: 2px !important;
    }
    .receipt-container table {
      width: 100% !important;
      table-layout: auto !important;
      border-collapse: collapse !important;
      margin: 0 !important;
      font-size: 9px !important;
    }
    .receipt-container table th,
    .receipt-container table td {
      padding: 1px 2px !important;
      box-sizing: border-box !important;
      vertical-align: top !important;
    }
    .receipt-container table th:first-child,
    .receipt-container table td:first-child {
      padding-left: 0 !important;
      padding-right: 1px !important;
    }
    .receipt-container table th:nth-child(2),
    .receipt-container table td:nth-child(2) {
      padding-left: 1px !important;
      padding-right: 1px !important;
    }
    .receipt-container table td:last-child,
    .receipt-container table th:last-child {
      text-align: right !important;
      white-space: nowrap !important;
      font-variant-numeric: tabular-nums !important;
      padding-right: 0 !important;
      padding-left: 2px !important;
    }
    .receipt-container .receipt-print-summary-num,
    .receipt-container .receipt-print-total-num {
      font-size: 9px !important;
      padding-right: 0 !important;
    }
    .receipt-container .receipt-print-total-label {
      font-size: 9px !important;
    }
    .receipt-container .receipt-print-total-num {
      font-size: 10px !important;
    }
    .receipt-container .receipt-print-line-price,
    .receipt-container .receipt-print-price-heading {
      padding-right: 0 !important;
    }
    .receipt-container .grid.grid-cols-4 {
      font-size: 7px !important;
      gap: 1px !important;
    }
  }
  .receipt-container {
    word-wrap: break-word;
    overflow-wrap: break-word;
    padding: 0.125rem;
    max-width: 48mm;
  }
  .receipt-container * {
    word-wrap: break-word;
    overflow-wrap: break-word;
  }
`
