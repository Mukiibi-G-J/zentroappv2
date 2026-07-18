export function formatReceiptAmount(
  value: number | string | null | undefined,
): string {
  if (value === null || value === undefined) {
    return "0";
  }
  const n = typeof value === "string" ? parseFloat(value) : value;
  if (!Number.isFinite(n)) {
    return "0";
  }
  return Math.round(n).toLocaleString("en-US");
}

export function formatReceiptDate(isoOrDate: string): string {
  try {
    const d = new Date(isoOrDate);
    if (isNaN(d.getTime())) {
      return String(isoOrDate).split("T")[0] || "";
    }
    return d
      .toLocaleString("en-GB", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
        timeZone: "Africa/Kampala",
      })
      .replace(",", "");
  } catch {
    return String(isoOrDate).split("T")[0] || "";
  }
}

/** Max columns for 58mm thermal; wider paper may use more. */
export function effectiveReceiptCols(
  cols: number,
  widthMm = 58,
): number {
  const requested = Number.isFinite(cols) && cols > 0 ? cols : 32;
  if (widthMm <= 58) {
    return Math.min(requested, 32);
  }
  if (widthMm <= 80) {
    return Math.min(requested, 42);
  }
  return requested;
}

export function padReceiptColumns(
  left: string,
  right: string,
  cols: number,
): string {
  const rightPart = String(right ?? "");
  const maxLeft = Math.max(1, cols - rightPart.length - 1);
  let leftPart = String(left ?? "");
  if (leftPart.length > maxLeft) {
    leftPart =
      maxLeft > 3 ? `${leftPart.slice(0, maxLeft - 3)}...` : leftPart.slice(0, maxLeft);
  }
  const gap = cols - leftPart.length - rightPart.length;
  return leftPart + (gap > 0 ? " ".repeat(gap) : " ") + rightPart;
}

export function cleanPaymentMethodLabel(desc?: string): string {
  if (!desc) return "";
  return desc.replace(/\s+cust\.?$/i, "").trim();
}
