/** Default thermal format strings (competitor-style {placeholder} syntax). */

export const DEFAULT_SALE_FORMAT_STRING = `{logo}
{company_name}
{address}
{phone}
--------------------------------
Receipt: {invoice_no}
Date: {date}
Customer: {customer_name}
Cashier: {cashier}
--------------------------------
{line_items}
--------------------------------
Total: {total}
Payment: {payment_method}
Change: {change}
--------------------------------
Thank you for your purchase!
Please come again
Receipt ID: {invoice_no}
--------------------------------
www.zentroapp.app
Contact: 0750440865 / 0779899789
Powered by Zentroapp`;

export const DEFAULT_PREPAYMENT_FORMAT_STRING = `{logo}
{company_name}
--------------------------------
Payment #: {invoice_no}
Date: {date}
Customer: {customer_name}
--------------------------------
{line_items}
--------------------------------
Total: {total}
Payment: {payment_method}
--------------------------------
Thank you for your purchase!
Please come again
Receipt ID: {document_no}
--------------------------------
www.zentroapp.app
Contact: 0750440865 / 0779899789
Powered by Zentroapp`;

export const DEFAULT_KOT_FORMAT_STRING = `KITCHEN ORDER
Order: {order_no}
Table: {table}
Type: {order_type}
Waiter: {waiter}
Time: {datetime}
--------------------------------
{items}
--------------------------------
*** KITCHEN COPY ***
--------------------------------
www.zentroapp.app
Contact: 0750440865 / 0779899789
Powered by Zentroapp`;

export const DEFAULT_BAR_FORMAT_STRING = `BAR ORDER
Order: {order_no}
Table: {table}
Time: {datetime}
--------------------------------
{items}
--------------------------------
*** BAR COPY ***
--------------------------------
www.zentroapp.app
Contact: 0750440865 / 0779899789
Powered by Zentroapp`;

export const DEFAULT_PAYMENT_JOURNAL_FORMAT_STRING = `PAYMENT RECEIPT
{company_name}
Doc: {document_no}
Date: {date}
--------------------------------
{line_items}
--------------------------------
Total: {total}
Payment: {payment_method}
--------------------------------
Thank you for your purchase!
Please come again
Receipt ID: {document_no}
--------------------------------
www.zentroapp.app
Contact: 0750440865 / 0779899789
Powered by Zentroapp`;

export function defaultFormatStringForType(receiptType: string): string {
  switch (receiptType) {
    case "prepayment":
      return DEFAULT_PREPAYMENT_FORMAT_STRING;
    case "kot":
      return DEFAULT_KOT_FORMAT_STRING;
    case "bar":
      return DEFAULT_BAR_FORMAT_STRING;
    case "payment_journal":
      return DEFAULT_PAYMENT_JOURNAL_FORMAT_STRING;
    default:
      return DEFAULT_SALE_FORMAT_STRING;
  }
}

export type FormatStringVariable = {
  key: string;
  label: string;
  description?: string;
  block?: boolean;
};

export const FORMAT_STRING_VARIABLES: Record<string, FormatStringVariable[]> = {
  sale: [
    { key: "logo", label: "Logo", block: true },
    { key: "company_name", label: "Company name" },
    { key: "address", label: "Address" },
    { key: "phone", label: "Phone" },
    { key: "email", label: "Email" },
    { key: "tin", label: "TIN" },
    { key: "branch", label: "Branch" },
    { key: "invoice_no", label: "Invoice / receipt no." },
    { key: "date", label: "Date" },
    { key: "time", label: "Time" },
    { key: "datetime", label: "Date & time" },
    { key: "customer_name", label: "Customer" },
    { key: "cashier", label: "Cashier" },
    { key: "line_items", label: "Line items", block: true },
    { key: "total", label: "Total" },
    { key: "subtotal", label: "Subtotal" },
    { key: "tax", label: "Tax" },
    { key: "discount", label: "Discount" },
    { key: "vat_amount", label: "VAT amount" },
    { key: "payment_method", label: "Payment method" },
    { key: "change", label: "Change" },
    { key: "amount_received", label: "Amount received" },
  ],
  prepayment: [
    { key: "logo", label: "Logo", block: true },
    { key: "company_name", label: "Company name" },
    { key: "invoice_no", label: "Payment no." },
    { key: "date", label: "Date" },
    { key: "customer_name", label: "Customer" },
    { key: "line_items", label: "Line items", block: true },
    { key: "total", label: "Total" },
    { key: "payment_method", label: "Payment method" },
  ],
  kot: [
    { key: "order_no", label: "Order no." },
    { key: "table", label: "Table" },
    { key: "order_type", label: "Order type" },
    { key: "waiter", label: "Waiter" },
    { key: "datetime", label: "Date & time" },
    { key: "items", label: "Items", block: true },
  ],
  bar: [
    { key: "order_no", label: "Order no." },
    { key: "table", label: "Table" },
    { key: "datetime", label: "Date & time" },
    { key: "items", label: "Items", block: true },
  ],
  payment_journal: [
    { key: "company_name", label: "Company name" },
    { key: "document_no", label: "Document no." },
    { key: "date", label: "Date" },
    { key: "line_items", label: "Line items", block: true },
    { key: "total", label: "Total" },
    { key: "payment_method", label: "Payment method" },
  ],
};
