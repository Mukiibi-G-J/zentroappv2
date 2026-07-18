import type { LayoutPreset, ReceiptType, ResolvedReceiptTemplate } from "./types";

const SALE_STANDARD_SECTIONS = [
  { id: "logo", enabled: true, order: 10, config: {} },
  { id: "title", enabled: true, order: 20, config: { text: "SALES RECEIPT" } },
  { id: "company_block", enabled: true, order: 30, config: {} },
  { id: "branch_line", enabled: true, order: 40, config: {} },
  { id: "receipt_meta", enabled: true, order: 50, config: {} },
  { id: "customer_line", enabled: true, order: 60, config: {} },
  { id: "line_items_compact", enabled: true, order: 70, config: {} },
  { id: "totals", enabled: true, order: 80, config: {} },
  { id: "vat_breakdown", enabled: true, order: 90, config: {} },
  { id: "tender_change", enabled: true, order: 100, config: {} },
  { id: "payment_method", enabled: true, order: 110, config: {} },
  { id: "footer_thanks", enabled: true, order: 120, config: {} },
  { id: "footer_receipt_id", enabled: true, order: 125, config: {} },
  {
    id: "footer_marketing",
    enabled: true,
    order: 130,
    config: {
      lines: [
        "www.zentroapp.app",
        "Contact: 0750440865 / 0779899789",
        "Powered by Zentroapp",
      ],
    },
  },
];

const SALE_COMPACT_SECTIONS = [
  ...SALE_STANDARD_SECTIONS.map((s) =>
    s.id === "footer_thanks"
      ? { ...s, config: { compact: true } }
      : s.id === "footer_receipt_id"
        ? { ...s, enabled: true }
        : s,
  ),
];

const KOT_SECTIONS = [
  { id: "title", enabled: true, order: 10, config: { text: "KITCHEN ORDER" } },
  { id: "order_meta", enabled: true, order: 20, config: {} },
  { id: "items", enabled: true, order: 30, config: {} },
  { id: "special_instructions", enabled: true, order: 40, config: {} },
  { id: "kitchen_copy_label", enabled: true, order: 50, config: { text: "*** KITCHEN COPY ***" } },
];

export function getFallbackTemplate(
  receiptType: ReceiptType,
  layoutPreset: LayoutPreset = "standard",
): ResolvedReceiptTemplate {
  const paper =
    layoutPreset === "compact"
      ? { widthMm: 58, charsPerLine: 32, logoWidthPx: 128 }
      : { widthMm: 58, charsPerLine: 42, logoWidthPx: 128 };

  if (receiptType === "kot") {
    return {
      code: "kot_compact_fallback",
      name: "KOT fallback",
      receiptType: "kot",
      layoutPreset: "compact",
      paperProfile: paper,
      sections: KOT_SECTIONS,
    };
  }

  if (receiptType === "bar") {
    return {
      code: "bar_compact_fallback",
      name: "Bar fallback",
      receiptType: "bar",
      layoutPreset: "compact",
      paperProfile: paper,
      sections: KOT_SECTIONS.map((s) =>
        s.id === "title"
          ? { ...s, config: { text: "BAR ORDER" } }
          : s.id === "kitchen_copy_label"
            ? { ...s, config: { text: "--- BAR ---" } }
            : s,
      ),
    };
  }

  if (receiptType === "interim_bill") {
    return {
      code: "interim_bill_fallback",
      name: "Guest check fallback",
      receiptType: "interim_bill",
      layoutPreset: "standard",
      paperProfile: paper,
      sections: [
        { id: "title", enabled: true, order: 10, config: { text: "GUEST CHECK" } },
        { id: "company_block", enabled: true, order: 20, config: {} },
        { id: "receipt_meta", enabled: true, order: 30, config: {} },
        { id: "customer_line", enabled: true, order: 40, config: {} },
        { id: "line_items_compact", enabled: true, order: 50, config: {} },
        { id: "totals", enabled: true, order: 60, config: {} },
        { id: "footer_thanks", enabled: true, order: 70, config: { text: "This is not a tax invoice." } },
      ],
    };
  }

  const isCompact = layoutPreset === "compact";
  return {
    code: isCompact ? "sale_compact_fallback" : "sale_standard_fallback",
    name: "Sale fallback",
    receiptType: receiptType === "prepayment" ? "prepayment" : "sale",
    layoutPreset,
    paperProfile: paper,
    sections: isCompact ? SALE_COMPACT_SECTIONS : SALE_STANDARD_SECTIONS,
  };
}
