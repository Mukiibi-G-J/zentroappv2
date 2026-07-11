"""
BC-style VAT calculation and posting setup utilities.
"""

from decimal import Decimal
from typing import Optional, Tuple

from postings.models import VATPostingSetup, VATBusinessPostingGroup, VATProductPostingGroup


def get_vat_posting_setup(
    vat_business_group: Optional[VATBusinessPostingGroup],
    vat_product_group: Optional[VATProductPostingGroup],
) -> Optional[VATPostingSetup]:
    """Resolve VAT Posting Setup from business + product posting groups."""
    if not vat_business_group or not vat_product_group:
        return None
    try:
        return VATPostingSetup.objects.get(
            vat_business_posting_group=vat_business_group,
            vat_product_posting_group=vat_product_group,
        )
    except VATPostingSetup.DoesNotExist:
        return None


def compute_line_vat(
    line_amount_excl_vat: Decimal,
    vat_percent: Decimal,
    prices_including_vat: bool = False,
) -> Tuple[Decimal, Decimal]:
    """
    Compute VAT amount and base amount.

    Args:
        line_amount_excl_vat: Line amount (excl. VAT if prices_including_vat=False, incl. if True).
        vat_percent: VAT percentage (e.g. 18.00).
        prices_including_vat: If True, line_amount_excl_vat is actually incl. VAT.

    Returns:
        (vat_amount, base_amount) where base_amount is the amount excl. VAT.
    """
    if vat_percent is None or vat_percent <= 0:
        return Decimal("0"), line_amount_excl_vat

    if prices_including_vat:
        # base = amount / (1 + vat/100)
        factor = Decimal("1") + (vat_percent / Decimal("100"))
        base_amount = (line_amount_excl_vat / factor).quantize(Decimal("0.01"))
        vat_amount = line_amount_excl_vat - base_amount
        return vat_amount, base_amount
    else:
        base_amount = line_amount_excl_vat
        vat_amount = (base_amount * vat_percent / Decimal("100")).quantize(Decimal("0.01"))
        return vat_amount, base_amount
