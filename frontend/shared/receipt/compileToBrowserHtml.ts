import type { ReceiptDocument, ReceiptDocumentNode } from "./types";

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function nodeToHtml(node: ReceiptDocumentNode): string {
  const style = node.style || {};
  const align = style.align || "left";
  const bold = style.bold ? "font-weight:bold;" : "";
  const dbl = style.double ? "font-size:1.15em;" : "";

  switch (node.type) {
    case "image":
      return node.src
        ? `<div style="text-align:center;margin:4px 0;"><img src="${escapeHtml(node.src)}" style="max-width:48mm;max-height:24mm;object-fit:contain;" alt="" /></div>`
        : "";
    case "text":
      return `<div style="text-align:${align};${bold}${dbl}">${escapeHtml(node.text || "")}</div>`;
    case "row":
      return `<div style="display:flex;justify-content:space-between;gap:8px;white-space:nowrap;${bold}"><span style="flex-shrink:0;">${escapeHtml(node.left || "")}</span><span style="text-align:right;flex:1;">${escapeHtml(node.right || "")}</span></div>`;
    case "rule":
      return `<hr style="border:none;border-top:1px dashed #000;margin:4px 0;" />`;
    case "feed":
      return "<br />".repeat(node.lines || 1);
    case "cut":
      return "";
    default:
      return "";
  }
}

export function compileDocumentToBrowserHtml(document: ReceiptDocument): string {
  const body = document.nodes.map(nodeToHtml).join("\n");
  const widthMm = document.paperProfile?.widthMm ?? 58;
  return `<!DOCTYPE html><html><head><meta charset="utf-8" /><style>
    @page { size: ${widthMm}mm auto; margin: 2mm; }
    body { font-family: monospace; font-size: 11px; width: ${widthMm}mm; margin: 0 auto; }
  </style></head><body>${body}</body></html>`;
}
