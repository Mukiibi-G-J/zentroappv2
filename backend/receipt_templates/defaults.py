"""Default section definitions and paper profiles for seeded receipt templates."""

DEFAULT_PAPER_WEB = {"widthMm": 58, "charsPerLine": 42, "logoWidthPx": 128}
DEFAULT_PAPER_MOBILE = {"widthMm": 58, "charsPerLine": 32, "logoWidthPx": 128}
DEFAULT_PAPER_DESKTOP = {"widthMm": 58, "charsPerLine": 42, "logoWidthPx": 128}

SALE_SECTIONS_STANDARD = [
    {"id": "logo", "enabled": True, "order": 10, "config": {}},
    {"id": "title", "enabled": True, "order": 20, "config": {"text": "SALES RECEIPT"}},
    {"id": "company_block", "enabled": True, "order": 30, "config": {}},
    {"id": "branch_line", "enabled": True, "order": 40, "config": {}},
    {"id": "receipt_meta", "enabled": True, "order": 50, "config": {}},
    {"id": "customer_line", "enabled": True, "order": 60, "config": {}},
    {"id": "line_items", "enabled": True, "order": 70, "config": {}},
    {"id": "totals", "enabled": True, "order": 80, "config": {}},
    {"id": "vat_breakdown", "enabled": True, "order": 90, "config": {}},
    {"id": "tender_change", "enabled": True, "order": 100, "config": {}},
    {"id": "payment_method", "enabled": True, "order": 110, "config": {}},
    {"id": "footer_thanks", "enabled": True, "order": 120, "config": {}},
    {"id": "footer_marketing", "enabled": True, "order": 130, "config": {
        "lines": [
            "www.zentroapp.app",
            "Contact: 0750440865 / 0779899789",
            "Powered by Zentroapp",
        ]
    }},
    {"id": "footer_receipt_id", "enabled": True, "order": 125, "config": {}},
    {"id": "qr_code", "enabled": False, "order": 150, "config": {}},
]

SALE_SECTIONS_COMPACT = [
    {"id": "logo", "enabled": True, "order": 10, "config": {}},
    {"id": "title", "enabled": True, "order": 20, "config": {"text": "SALES RECEIPT"}},
    {"id": "company_block", "enabled": True, "order": 30, "config": {}},
    {"id": "receipt_meta", "enabled": True, "order": 40, "config": {}},
    {"id": "customer_line", "enabled": True, "order": 50, "config": {}},
    {"id": "line_items_compact", "enabled": True, "order": 60, "config": {}},
    {"id": "totals", "enabled": True, "order": 70, "config": {}},
    {"id": "tender_change", "enabled": True, "order": 80, "config": {}},
    {"id": "payment_method", "enabled": True, "order": 90, "config": {}},
    {"id": "footer_thanks", "enabled": True, "order": 100, "config": {}},
    {"id": "footer_receipt_id", "enabled": True, "order": 110, "config": {}},
    {"id": "footer_marketing", "enabled": True, "order": 120, "config": {
        "lines": [
            "www.zentroapp.app",
            "Contact: 0750440865 / 0779899789",
            "Powered by Zentroapp",
        ]
    }},
]

PREPAYMENT_SECTIONS_STANDARD = [
    {"id": "logo", "enabled": True, "order": 10, "config": {}},
    {"id": "title", "enabled": True, "order": 20, "config": {"text": "PAYMENT RECEIPT"}},
    {"id": "company_block", "enabled": True, "order": 30, "config": {}},
    {"id": "receipt_meta", "enabled": True, "order": 40, "config": {"variant": "prepayment"}},
    {"id": "customer_line", "enabled": True, "order": 50, "config": {"variant": "prepayment"}},
    {"id": "line_items_compact", "enabled": True, "order": 60, "config": {}},
    {"id": "totals", "enabled": True, "order": 70, "config": {"variant": "prepayment"}},
    {"id": "payment_method", "enabled": True, "order": 80, "config": {"variant": "prepayment"}},
    {"id": "footer_thanks", "enabled": True, "order": 90, "config": {}},
    {"id": "footer_receipt_id", "enabled": True, "order": 95, "config": {}},
    {"id": "footer_marketing", "enabled": True, "order": 100, "config": {
        "lines": [
            "www.zentroapp.app",
            "Contact: 0750440865 / 0779899789",
            "Powered by Zentroapp",
        ]
    }},
]

KOT_SECTIONS = [
    {"id": "title", "enabled": True, "order": 10, "config": {"text": "KITCHEN ORDER"}},
    {"id": "order_meta", "enabled": True, "order": 20, "config": {}},
    {"id": "items", "enabled": True, "order": 30, "config": {}},
    {"id": "special_instructions", "enabled": True, "order": 40, "config": {}},
    {"id": "kitchen_copy_label", "enabled": True, "order": 50, "config": {"text": "*** KITCHEN COPY ***"}},
]

BAR_SECTIONS = [
    {"id": "title", "enabled": True, "order": 10, "config": {"text": "BAR ORDER"}},
    {"id": "order_meta", "enabled": True, "order": 20, "config": {}},
    {"id": "items", "enabled": True, "order": 30, "config": {}},
    {"id": "kitchen_copy_label", "enabled": True, "order": 40, "config": {"text": "*** BAR COPY ***"}},
]

INTERIM_BILL_SECTIONS = [
    {"id": "logo", "enabled": True, "order": 10, "config": {}},
    {"id": "title", "enabled": True, "order": 20, "config": {"text": "GUEST CHECK"}},
    {"id": "company_block", "enabled": True, "order": 30, "config": {}},
    {"id": "branch_line", "enabled": True, "order": 40, "config": {}},
    {"id": "receipt_meta", "enabled": True, "order": 50, "config": {"variant": "interim_bill"}},
    {"id": "customer_line", "enabled": True, "order": 60, "config": {}},
    {"id": "line_items", "enabled": True, "order": 70, "config": {}},
    {"id": "totals", "enabled": True, "order": 80, "config": {}},
    {"id": "footer_thanks", "enabled": True, "order": 90, "config": {"text": "This is not a tax invoice."}},
    {"id": "footer_marketing", "enabled": True, "order": 100, "config": {
        "lines": ["Powered by Zentroapp"],
    }},
]

PAYMENT_JOURNAL_SECTIONS = [
    {"id": "title", "enabled": True, "order": 10, "config": {"text": "PAYMENT RECEIPT"}},
    {"id": "company_block", "enabled": True, "order": 20, "config": {}},
    {"id": "receipt_meta", "enabled": True, "order": 30, "config": {}},
    {"id": "line_items", "enabled": True, "order": 40, "config": {}},
    {"id": "totals", "enabled": True, "order": 50, "config": {}},
    {"id": "footer_thanks", "enabled": True, "order": 60, "config": {}},
    {"id": "footer_receipt_id", "enabled": True, "order": 65, "config": {}},
    {"id": "footer_marketing", "enabled": True, "order": 70, "config": {
        "lines": [
            "www.zentroapp.app",
            "Contact: 0750440865 / 0779899789",
            "Powered by Zentroapp",
        ]
    }},
]

DEFAULT_SALE_FORMAT_STRING = """{logo}
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
Thank you for your business!"""

DEFAULT_PREPAYMENT_FORMAT_STRING = """{logo}
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
Thank you!"""

DEFAULT_KOT_FORMAT_STRING = """KITCHEN ORDER
Order: {order_no}
Table: {table}
Type: {order_type}
Waiter: {waiter}
Time: {datetime}
--------------------------------
{items}
--------------------------------
*** KITCHEN COPY ***"""

DEFAULT_INTERIM_BILL_FORMAT_STRING = """{logo}
{company_name}
--------------------------------
GUEST CHECK
Order: {order_no}
Table: {table}
Date: {date}
Waiter: {waiter}
--------------------------------
{line_items}
--------------------------------
Total: {total}
--------------------------------
This is not a tax invoice."""

DEFAULT_BAR_FORMAT_STRING = """BAR ORDER
Order: {order_no}
Table: {table}
Time: {datetime}
--------------------------------
{items}
--------------------------------
*** BAR COPY ***"""

DEFAULT_PAYMENT_JOURNAL_FORMAT_STRING = """PAYMENT RECEIPT
{company_name}
Doc: {document_no}
Date: {date}
--------------------------------
{line_items}
--------------------------------
Total: {total}
Payment: {payment_method}
--------------------------------
Thank you!"""

SYSTEM_TEMPLATES = [
    {
        "code": "sale_standard",
        "name": "Sale — Standard",
        "receipt_type": "sale",
        "layout_preset": "standard",
        "paper_profile": DEFAULT_PAPER_WEB,
        "sections": SALE_SECTIONS_STANDARD,
    },
    {
        "code": "sale_compact",
        "name": "Sale — Compact",
        "receipt_type": "sale",
        "layout_preset": "compact",
        "paper_profile": DEFAULT_PAPER_MOBILE,
        "sections": SALE_SECTIONS_COMPACT,
    },
    {
        "code": "prepayment_standard",
        "name": "Prepayment — Standard",
        "receipt_type": "prepayment",
        "layout_preset": "standard",
        "paper_profile": DEFAULT_PAPER_WEB,
        "sections": PREPAYMENT_SECTIONS_STANDARD,
    },
    {
        "code": "kot_compact",
        "name": "Kitchen order — Compact",
        "receipt_type": "kot",
        "layout_preset": "compact",
        "paper_profile": DEFAULT_PAPER_MOBILE,
        "sections": KOT_SECTIONS,
    },
    {
        "code": "bar_compact",
        "name": "Bar order — Compact",
        "receipt_type": "bar",
        "layout_preset": "compact",
        "paper_profile": DEFAULT_PAPER_MOBILE,
        "sections": BAR_SECTIONS,
    },
    {
        "code": "interim_bill_standard",
        "name": "Guest check — Standard",
        "receipt_type": "interim_bill",
        "layout_preset": "standard",
        "paper_profile": DEFAULT_PAPER_WEB,
        "sections": INTERIM_BILL_SECTIONS,
    },
    {
        "code": "payment_journal_standard",
        "name": "Payment journal — Standard",
        "receipt_type": "payment_journal",
        "layout_preset": "standard",
        "paper_profile": DEFAULT_PAPER_WEB,
        "sections": PAYMENT_JOURNAL_SECTIONS,
    },
]

# Default assignments: (template_code, device, printer, process, priority)
DEFAULT_ASSIGNMENTS = [
    ("sale_standard", "web", "serial", "pos_sale", 100),
    ("sale_standard", "web", "browser", "pos_sale", 90),
    ("sale_compact", "web", "browser", "sales_history_reprint", 100),
    ("sale_compact", "web", "serial", "sales_history_reprint", 90),
    ("sale_standard", "mobile", "sunmi", "pos_sale", 100),
    ("sale_standard", "mobile", "bluetooth", "pos_sale", 100),
    ("sale_standard", "mobile", "usb", "pos_sale", 100),
    ("sale_compact", "mobile", "any", "sales_history_reprint", 100),
    # Restaurant settle — web browser print (counter / dine-in checkout)
    ("sale_standard", "web", "browser", "restaurant_settle", 100),
    ("sale_standard", "web", "serial", "restaurant_settle", 90),
    ("sale_standard", "desktop", "desktop_silent", "restaurant_settle", 100),
    ("sale_standard", "mobile", "any", "restaurant_settle", 100),
    ("sale_standard", "any", "any", "restaurant_settle", 50),
    ("sale_standard", "desktop", "desktop_silent", "pos_sale", 100),
    ("prepayment_standard", "any", "any", "prepayment_post", 100),
    ("kot_compact", "any", "any", "restaurant_kot", 100),
    ("bar_compact", "any", "any", "restaurant_bar", 100),
    ("interim_bill_standard", "any", "browser", "restaurant_guest_check", 100),
    ("interim_bill_standard", "web", "browser", "restaurant_guest_check", 90),
    ("payment_journal_standard", "any", "browser", "payment_journal", 100),
    ("payment_journal_standard", "any", "any", "payment_journal", 50),
]
