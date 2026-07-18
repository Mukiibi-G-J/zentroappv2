import type { ReceiptType, TemplateSection } from "./types";

export type SectionCatalogEntry = {
  id: string;
  label: string;
  description?: string;
  defaultConfig?: Record<string, unknown>;
};

const SALE_SECTIONS: SectionCatalogEntry[] = [
  { id: "logo", label: "Company logo" },
  { id: "title", label: "Receipt title", defaultConfig: { text: "SALES RECEIPT" } },
  { id: "company_block", label: "Company details" },
  { id: "branch_line", label: "Branch name" },
  { id: "receipt_meta", label: "Invoice no. & date" },
  { id: "customer_line", label: "Customer" },
  { id: "line_items", label: "Line items (detailed)" },
  { id: "line_items_compact", label: "Line items (compact)" },
  { id: "totals", label: "Totals" },
  { id: "vat_breakdown", label: "VAT breakdown" },
  { id: "tender_change", label: "Tender & change" },
  { id: "payment_method", label: "Payment method" },
  { id: "footer_thanks", label: "Thank you footer" },
  {
    id: "footer_marketing",
    label: "Marketing footer",
    defaultConfig: {
      lines: [
        "www.zentroapp.app",
        "Contact: 0750440865 / 0779899789",
        "Powered by Zentroapp",
      ],
    },
  },
  { id: "footer_receipt_id", label: "Receipt ID footer" },
  { id: "qr_code", label: "QR code" },
];

const PREPAYMENT_SECTIONS: SectionCatalogEntry[] = [
  { id: "logo", label: "Company logo" },
  { id: "title", label: "Title", defaultConfig: { text: "PAYMENT RECEIPT" } },
  { id: "company_block", label: "Company details" },
  { id: "receipt_meta", label: "Payment meta", defaultConfig: { variant: "prepayment" } },
  { id: "customer_line", label: "Customer", defaultConfig: { variant: "prepayment" } },
  { id: "line_items_compact", label: "Line items" },
  { id: "totals", label: "Totals", defaultConfig: { variant: "prepayment" } },
  { id: "payment_method", label: "Payment method", defaultConfig: { variant: "prepayment" } },
  { id: "footer_thanks", label: "Thank you footer" },
];

const KOT_SECTIONS: SectionCatalogEntry[] = [
  { id: "title", label: "Title", defaultConfig: { text: "KITCHEN ORDER" } },
  { id: "order_meta", label: "Order details" },
  { id: "items", label: "Items" },
  { id: "special_instructions", label: "Special instructions" },
  { id: "kitchen_copy_label", label: "Kitchen copy label", defaultConfig: { text: "*** KITCHEN COPY ***" } },
];

const BAR_SECTIONS: SectionCatalogEntry[] = [
  { id: "title", label: "Title", defaultConfig: { text: "BAR ORDER" } },
  { id: "order_meta", label: "Order details" },
  { id: "items", label: "Items" },
  { id: "kitchen_copy_label", label: "Bar copy label", defaultConfig: { text: "*** BAR COPY ***" } },
];

const PAYMENT_JOURNAL_SECTIONS: SectionCatalogEntry[] = [
  { id: "title", label: "Title", defaultConfig: { text: "PAYMENT RECEIPT" } },
  { id: "company_block", label: "Company details" },
  { id: "receipt_meta", label: "Document meta" },
  { id: "line_items", label: "Line items" },
  { id: "totals", label: "Totals" },
  { id: "footer_thanks", label: "Thank you footer" },
];

const INTERIM_BILL_SECTIONS: SectionCatalogEntry[] = [
  { id: "logo", label: "Company logo" },
  { id: "title", label: "Title", defaultConfig: { text: "GUEST CHECK" } },
  { id: "company_block", label: "Company details" },
  { id: "branch_line", label: "Branch name" },
  { id: "receipt_meta", label: "Order & table" },
  { id: "customer_line", label: "Customer" },
  { id: "line_items", label: "Line items" },
  { id: "totals", label: "Total" },
  { id: "footer_thanks", label: "Disclaimer", defaultConfig: { text: "This is not a tax invoice." } },
];

export const SECTION_CATALOG: Record<ReceiptType, SectionCatalogEntry[]> = {
  sale: SALE_SECTIONS,
  prepayment: PREPAYMENT_SECTIONS,
  kot: KOT_SECTIONS,
  bar: BAR_SECTIONS,
  interim_bill: INTERIM_BILL_SECTIONS,
  payment_journal: PAYMENT_JOURNAL_SECTIONS,
};

export function sectionLabel(receiptType: ReceiptType, sectionId: string): string {
  return SECTION_CATALOG[receiptType]?.find((s) => s.id === sectionId)?.label ?? sectionId;
}

export function nextSectionOrder(sections: TemplateSection[]): number {
  if (!sections.length) return 10;
  return Math.max(...sections.map((s) => s.order ?? 0)) + 10;
}

export function createSectionFromCatalog(
  receiptType: ReceiptType,
  sectionId: string,
  order: number,
): TemplateSection | null {
  const entry = SECTION_CATALOG[receiptType]?.find((s) => s.id === sectionId);
  if (!entry) return null;
  return {
    id: entry.id,
    enabled: true,
    order,
    config: entry.defaultConfig ? { ...entry.defaultConfig } : {},
  };
}
