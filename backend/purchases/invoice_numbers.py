import random
import string

from django.utils import timezone

from purchases.models import PurchaseInvoice


def generate_unique_vendor_invoice_no() -> str:
    """Internal reference when the user has no vendor bill number (PUR-YYYYMMDD-######)."""
    today_str = timezone.now().strftime('%Y%m%d')
    while True:
        candidate = f'PUR-{today_str}-' + ''.join(random.choices(string.digits, k=6))
        if not PurchaseInvoice.objects.filter(vendor_invoice_no=candidate).exists():
            return candidate


def ensure_purchase_invoice_vendor_invoice_no(invoice) -> bool:
    """
    Assign vendor_invoice_no when blank so posting can succeed.
    Returns True when a new number was generated and saved.
    """
    current = (invoice.vendor_invoice_no or '').strip()
    if current:
        return False

    invoice.vendor_invoice_no = generate_unique_vendor_invoice_no()
    invoice.save(update_fields=['vendor_invoice_no', 'updated_at'])
    return True
