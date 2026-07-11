"""
Helpers to keep Inventory Posting Setup aligned with branch Locations.

Sales invoice posting requires an exact (location, inventory_posting_group) row.
Company onboarding seeds company-wide defaults with location=NULL; each branch
Location needs copies of those rows.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from items.models import Location

logger = logging.getLogger(__name__)


def ensure_inventory_posting_setups_for_location(location: "Location") -> int:
    """
    For each company-default InventoryPostingSetup (location is NULL), ensure a
    matching row exists for ``location``. Returns the number of rows created.
    """
    from postings.models import InventoryPostingSetup

    if not location or not getattr(location, "code", None):
        return 0

    created = 0
    defaults = InventoryPostingSetup.objects.filter(location__isnull=True).select_related(
        "inventory_account", "wip_account", "inventory_posting_group"
    )
    for template in defaults:
        _, was_created = InventoryPostingSetup.objects.get_or_create(
            location=location,
            inventory_posting_group=template.inventory_posting_group,
            defaults={
                "inventory_account": template.inventory_account,
                "wip_account": template.wip_account,
            },
        )
        if was_created:
            created += 1
            logger.info(
                "Created InventoryPostingSetup for location %s, group %s",
                location.code,
                template.inventory_posting_group_id,
            )
    return created


def ensure_inventory_posting_setups_for_all_locations() -> int:
    """Ensure every Location has location-specific setups copied from defaults."""
    from items.models import Location

    total = 0
    for location in Location.objects.all().only("code"):
        total += ensure_inventory_posting_setups_for_location(location)
    return total
