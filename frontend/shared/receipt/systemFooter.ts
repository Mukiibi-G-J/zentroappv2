import type {
  PaymentJournalPayload,
  ReceiptBuildPayload,
  ReceiptDocumentNode,
  SaleReceiptPayload,
} from "./types";

/** Zentro branding — appended to every receipt when not already present. */
export const SYSTEM_MARKETING_LINES = [
  "www.zentroapp.app",
  "Contact: 0750440865 / 0779899789",
  "Powered by Zentroapp",
] as const;

function nodeText(nodes: ReceiptDocumentNode[]): string {
  return nodes
    .map((n) => [n.text, n.left, n.right].filter(Boolean).join(" "))
    .join("\n");
}

export function hasSystemMarketingBlock(nodes: ReceiptDocumentNode[]): boolean {
  const blob = nodeText(nodes).toLowerCase();
  return (
    blob.includes("zentroapp.app") || blob.includes("powered by zentroapp")
  );
}

export function hasCustomerThanksBlock(nodes: ReceiptDocumentNode[]): boolean {
  const blob = nodeText(nodes).toLowerCase();
  return (
    blob.includes("thank you for your purchase") ||
    blob.includes("please come again")
  );
}

function receiptIdForPayload(payload: ReceiptBuildPayload): string {
  if (payload.receiptType === "payment_journal") {
    return (payload as PaymentJournalPayload).documentNo || "";
  }
  if (payload.receiptType === "sale" || payload.receiptType === "prepayment") {
    return (payload as SaleReceiptPayload).invoiceNo || "";
  }
  return "";
}

/** Customer-facing receipts: thanks + receipt id + marketing. */
export function appendMandatorySystemFooter(
  nodes: ReceiptDocumentNode[],
  payload: ReceiptBuildPayload,
): void {
  const customerFacing =
    payload.receiptType === "sale" ||
    payload.receiptType === "prepayment" ||
    payload.receiptType === "payment_journal";

  if (customerFacing && !hasCustomerThanksBlock(nodes)) {
    nodes.push({
      type: "text",
      text: "Thank you for your purchase!",
      style: { align: "center" },
    });
    nodes.push({
      type: "text",
      text: "Please come again",
      style: { align: "center" },
    });
    const receiptId = receiptIdForPayload(payload);
    if (receiptId) {
      nodes.push({
        type: "text",
        text: `Receipt ID: ${receiptId}`,
        style: { align: "center" },
      });
    }
  }

  if (!hasSystemMarketingBlock(nodes)) {
    nodes.push({ type: "rule" });
    for (const line of SYSTEM_MARKETING_LINES) {
      nodes.push({ type: "text", text: line, style: { align: "center" } });
    }
  }

  nodes.push({ type: "feed", lines: 1 });
}
