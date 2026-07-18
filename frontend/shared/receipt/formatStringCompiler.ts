import {
  cleanPaymentMethodLabel,
  formatReceiptAmount,
  formatReceiptDate,
} from "./formatters";
import type {
  KotBarPayload,
  PaymentJournalPayload,
  ReceiptBranding,
  ReceiptBuildPayload,
  ReceiptDocumentNode,
  ReceiptLineItem,
  SaleReceiptPayload,
} from "./types";

function lineTotal(item: ReceiptLineItem): number {
  if (item.line_total != null && Number.isFinite(item.line_total)) {
    return item.line_total;
  }
  const tp = item.total_price ?? item.total_amount;
  if (tp != null) {
    const v = typeof tp === "string" ? parseFloat(tp) : tp;
    if (Number.isFinite(v)) return v;
  }
  const q = Number(item.quantity) || 0;
  const u = Number(item.unit_price) || 0;
  return q * u;
}

function isRuleLine(line: string): boolean {
  const t = line.trim();
  return t.length >= 3 && /^[-=_*]{3,}$/.test(t);
}

function saleVariables(
  payload: SaleReceiptPayload,
  branding: ReceiptBranding,
): Record<string, string> {
  const branch = (branding.branchCode || "").split(/\r?\n/)[0]?.trim() || "";
  return {
    company_name: branding.displayName || branding.name || "",
    display_name: branding.displayName || branding.name || "",
    address: branding.address || "",
    phone: branding.phone || "",
    email: branding.email || "",
    tin: branding.tin || "",
    vat_no: branding.vatNo || "",
    branch,
    invoice_no: payload.invoiceNo || "",
    receipt_no: payload.invoiceNo || "",
    date: formatReceiptDate(payload.documentDate),
    time: new Date(payload.documentDate).toLocaleTimeString(),
    datetime: `${formatReceiptDate(payload.documentDate)} ${new Date(payload.documentDate).toLocaleTimeString()}`,
    customer_name: payload.customerName || "",
    customer_no: payload.customerNo || "",
    cashier: payload.sellerName || "",
    seller: payload.sellerName || "",
    total: formatReceiptAmount(payload.totalAmount),
    subtotal: payload.subtotal != null ? formatReceiptAmount(payload.subtotal) : "",
    tax: payload.tax != null ? formatReceiptAmount(payload.tax) : "",
    discount: payload.discount != null ? formatReceiptAmount(payload.discount) : "",
    vat_amount:
      payload.vatAmount != null ? formatReceiptAmount(payload.vatAmount) : "",
    payment_method: cleanPaymentMethodLabel(payload.paymentMethod || ""),
    change:
      payload.changeAmount != null ? formatReceiptAmount(payload.changeAmount) : "",
    amount_received:
      payload.amountReceived != null
        ? formatReceiptAmount(payload.amountReceived)
        : "",
    tendered:
      payload.amountReceived != null
        ? formatReceiptAmount(payload.amountReceived)
        : "",
  };
}

function kotVariables(payload: KotBarPayload): Record<string, string> {
  return {
    order_no: payload.orderNo || "",
    table: payload.tableLabel || "",
    order_type: payload.orderTypeDisplay || "",
    waiter: payload.waiterName || "",
    date: formatReceiptDate(payload.printedAt),
    time: new Date(payload.printedAt).toLocaleTimeString(),
    datetime: `${formatReceiptDate(payload.printedAt)} ${new Date(payload.printedAt).toLocaleTimeString()}`,
  };
}

function paymentJournalVariables(
  payload: PaymentJournalPayload,
  branding: ReceiptBranding,
): Record<string, string> {
  return {
    company_name: branding.displayName || branding.name || "",
    document_no: payload.documentNo || "",
    date: formatReceiptDate(payload.documentDate),
    total: formatReceiptAmount(payload.totalAmount),
    payment_method: cleanPaymentMethodLabel(payload.paymentMethod || ""),
  };
}

function appendSaleLineItems(
  nodes: ReceiptDocumentNode[],
  payload: SaleReceiptPayload,
): void {
  nodes.push({ type: "row", left: "Qty", right: "Amount", style: { bold: true } });
  nodes.push({ type: "rule" });
  for (const item of payload.lines) {
    const lt = lineTotal(item);
    const qty = item.quantity;
    const name = (item.item_name || "Item").trim();
    const short = name.length > 18 ? `${name.slice(0, 15)}...` : name;
    nodes.push({
      type: "row",
      left: `${qty}x ${short}`,
      right: formatReceiptAmount(lt),
    });
  }
  nodes.push({ type: "rule" });
}

function appendKotBarItems(
  nodes: ReceiptDocumentNode[],
  payload: KotBarPayload,
): void {
  for (const item of payload.items) {
    const qty = item.quantity;
    const name = (item.item_name || "Item").trim();
    nodes.push({ type: "text", text: `${qty}x ${name}`, style: { bold: true } });
    if (item.special_instructions) {
      nodes.push({ type: "text", text: `  Note: ${item.special_instructions}` });
    }
    if (item.fire_state_display) {
      nodes.push({ type: "text", text: `  ${item.fire_state_display}` });
    }
  }
}

function appendPaymentJournalLineItems(
  nodes: ReceiptDocumentNode[],
  payload: PaymentJournalPayload,
  cols: number,
): void {
  for (const item of payload.lines) {
    const lt = lineTotal(item);
    const left = `${item.quantity}x ${(item.item_name || "Item").trim()}`;
    nodes.push({
      type: "row",
      left: left.length > cols - 12 ? `${left.slice(0, cols - 15)}...` : left,
      right: formatReceiptAmount(lt),
    });
  }
  nodes.push({ type: "rule" });
}

function substituteLine(
  line: string,
  vars: Record<string, string>,
): string | null {
  const replaced = line.replace(/\{([a-z0-9_]+)\}/gi, (_, key: string) => {
    const k = key.toLowerCase();
    return vars[k] ?? "";
  });
  const trimmed = replaced.trim();
  if (!trimmed) return null;
  if (/^[^:]+:\s*$/.test(trimmed)) return null;
  return replaced;
}

export function compileFormatStringToNodes(
  formatString: string,
  payload: ReceiptBuildPayload,
  branding: ReceiptBranding,
  cols: number,
): ReceiptDocumentNode[] {
  const nodes: ReceiptDocumentNode[] = [];
  const lines = (formatString || "").split(/\r?\n/);

  let vars: Record<string, string> = {};
  if (payload.receiptType === "kot" || payload.receiptType === "bar") {
    vars = kotVariables(payload);
  } else if (payload.receiptType === "payment_journal") {
    vars = paymentJournalVariables(payload, branding);
  } else {
    vars = saleVariables(payload as SaleReceiptPayload, branding);
  }

  for (const rawLine of lines) {
    const trimmed = rawLine.trim();

    if (!trimmed) {
      nodes.push({ type: "feed", lines: 1 });
      continue;
    }

    if (isRuleLine(rawLine)) {
      nodes.push({ type: "rule" });
      continue;
    }

    const block = trimmed.toLowerCase();
    if (block === "{logo}") {
      if (branding.logo) {
        nodes.push({ type: "image", src: branding.logo, style: { align: "center" } });
        nodes.push({ type: "feed", lines: 1 });
      }
      continue;
    }

    if (block === "{line_items}") {
      if (payload.receiptType === "payment_journal") {
        appendPaymentJournalLineItems(nodes, payload, cols);
      } else if (payload.receiptType === "sale" || payload.receiptType === "prepayment") {
        appendSaleLineItems(nodes, payload as SaleReceiptPayload);
      }
      continue;
    }

    if (block === "{items}" && (payload.receiptType === "kot" || payload.receiptType === "bar")) {
      appendKotBarItems(nodes, payload);
      continue;
    }

    const text = substituteLine(rawLine, vars);
    if (text == null) continue;

    const rowMatch = text.match(/^(.+?):\s+(.+)$/);
    if (rowMatch && rowMatch[2].length <= 28) {
      nodes.push({
        type: "row",
        left: `${rowMatch[1]}:`,
        right: rowMatch[2],
      });
    } else {
      nodes.push({ type: "text", text });
    }
  }

  return nodes;
}
