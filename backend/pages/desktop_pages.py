"""
Pages exposed in the Zentro Desktop Electron client.

Nav items and direct page routes on desktop only show pages with
``desktop_enabled=True``. Web continues to show the full catalog.
"""

from __future__ import annotations

DESKTOP_ENABLED_PAGE_NAMES = frozenset(
    {
        'SalesPOS',
        'RestaurantPOS',
        'ItemList',
        'ItemCard',
        'CustomerList',
        'CustomerCard',
        'VendorList',
        'VendorCard',
        'DesktopSyncQueue',
    }
)


def sync_desktop_enabled_flags() -> int:
    """Reset all pages to disabled, then enable the desktop allow-list."""
    from pages.models import Page

    Page.objects.all().update(desktop_enabled=False)
    return Page.objects.filter(name__in=DESKTOP_ENABLED_PAGE_NAMES).update(desktop_enabled=True)
