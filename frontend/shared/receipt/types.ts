export type ReceiptType =
  | "sale"
  | "prepayment"
  | "kot"
  | "bar"
  | "interim_bill"
  | "payment_journal";

export type LayoutPreset = "compact" | "standard" | "detailed";

export type DeviceType = "web" | "mobile" | "desktop" | "any";
export type PrinterType =
  | "browser"
  | "serial"
  | "sunmi"
  | "bluetooth"
  | "usb"
  | "desktop_silent"
  | "any";

export type ReceiptProcess =
  | "pos_sale"
  | "sales_history_reprint"
  | "prepayment_post"
  | "restaurant_settle"
  | "restaurant_kot"
  | "restaurant_bar"
  | "restaurant_guest_check"
  | "payment_journal"
  | "any";

export type EditorMode = "visual" | "format_string";

export interface PaperProfile {
  widthMm?: number;
  heightMm?: number;
  charsPerLine?: number;
  logoWidthPx?: number;
}

export interface TemplateSection {
  id: string;
  enabled: boolean;
  order: number;
  config?: Record<string, unknown>;
}

export interface ResolvedReceiptTemplate {
  id?: number;
  code: string;
  name: string;
  receiptType: ReceiptType;
  layoutPreset: LayoutPreset;
  paperProfile: PaperProfile;
  sections: TemplateSection[];
  editorMode?: EditorMode;
  formatString?: string;
  isSystem?: boolean;
  isActive?: boolean;
}

export interface ReceiptBranding {
  name: string;
  displayName?: string;
  branchCode?: string;
  logo?: string | null;
  address?: string;
  phone?: string;
  email?: string;
  tin?: string;
  vatNo?: string;
}

export interface PrintContext {
  receiptType: ReceiptType;
  deviceType: DeviceType;
  printerType: PrinterType;
  process: ReceiptProcess;
  branchId?: number | null;
}

export interface ReceiptLineItem {
  item_name: string;
  quantity: number | string;
  unit_price?: number | string;
  total_price?: number | string;
  total_amount?: number | string;
  line_total?: number;
  special_instructions?: string | null;
  fire_state_display?: string | null;
  seat_no?: number | null;
}

export interface SaleReceiptPayload {
  receiptType: "sale" | "prepayment" | "interim_bill";
  invoiceNo: string;
  documentDate: string;
  customerName?: string;
  customerNo?: string;
  orderNo?: string;
  tableLabel?: string;
  orderTypeDisplay?: string;
  waiterName?: string;
  lines: ReceiptLineItem[];
  totalAmount: number;
  subtotal?: number;
  tax?: number;
  discount?: number;
  vatEnabled?: boolean;
  vatAmount?: number;
  totalExclVat?: number;
  amountReceived?: number;
  changeAmount?: number;
  paymentMethod?: string;
  paymentMethodCode?: string;
  sellerName?: string;
  prepaymentDocumentNo?: string;
  remainingBalance?: number;
}

export interface KotBarPayload {
  receiptType: "kot" | "bar";
  title?: string;
  orderNo: string;
  tableLabel: string;
  orderTypeDisplay: string;
  waiterName?: string;
  printedAt: string;
  items: ReceiptLineItem[];
}

export interface PaymentJournalPayload {
  receiptType: "payment_journal";
  documentNo: string;
  documentDate: string;
  lines: ReceiptLineItem[];
  totalAmount: number;
  paymentMethod?: string;
}

export type ReceiptBuildPayload =
  | SaleReceiptPayload
  | KotBarPayload
  | PaymentJournalPayload;

export type ReceiptNodeType =
  | "image"
  | "text"
  | "row"
  | "rule"
  | "feed"
  | "cut";

export interface ReceiptTextStyle {
  align?: "left" | "center" | "right";
  bold?: boolean;
  double?: boolean;
  size?: number;
}

export interface ReceiptDocumentNode {
  type: ReceiptNodeType;
  text?: string;
  left?: string;
  right?: string;
  src?: string;
  style?: ReceiptTextStyle;
  lines?: number;
}

export interface ReceiptDocument {
  paperProfile: PaperProfile;
  nodes: ReceiptDocumentNode[];
}

export interface ResolvedReceiptConfig {
  template: ResolvedReceiptTemplate;
  branding: ReceiptBranding;
}
