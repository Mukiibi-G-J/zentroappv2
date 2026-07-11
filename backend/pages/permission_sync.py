"""
Sync page-engine pages to base.Objects for BC-style permission lines.

Each Page with a non-null ``object_id`` becomes (or updates) a Page row in
``base.Objects`` using the same numeric ID as in permission sets — mirroring
how BC permission lines reference compiled page object IDs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from pages.bc_page_ids import module_for_page_name

if TYPE_CHECKING:
    from pages.models import Page


def _page_type_ref():
    from base.models import ObjectType

    page_type, _ = ObjectType.objects.get_or_create(
        code='PAGE',
        defaults={
            'name': 'Page',
            'description': 'UI pages (BC-style object permissions)',
            'sort_order': 2,
        },
    )
    return page_type


def _unique_page_object_name(page: 'Page') -> str:
    from base.models import Objects

    if not Objects.objects.filter(object_name=page.name).exclude(
        object_id=page.object_id,
    ).exists():
        return page.name
    return f'Page · {page.caption}'


def sync_page_permission_object(page: 'Page') -> tuple[object | None, bool]:
    """
    Upsert base.Objects for one page-engine page.

    Returns (Objects instance or None, created).
    """
    from base.models import Objects
    from permissions.models import PermissionSetLine

    if page.object_id is None:
        return None, False

    page_type = _page_type_ref()
    module = module_for_page_name(page.name) or _infer_module(page)
    defaults = {
        'object_type': 'Page',
        'object_type_ref': page_type,
        'object_caption': page.caption,
        'app_label': module,
        'object_subtype': 'Custom',
        'is_active': True,
        'requires_permission': True,
        'related_model': '',
    }

    existing_by_id = Objects.objects.filter(object_id=page.object_id).first()

    # Retire legacy Page rows that reused this engine name with an old module-based ID.
    for stale in Objects.objects.filter(
        object_type='Page',
        object_name=page.name,
    ).exclude(object_id=page.object_id):
        if existing_by_id:
            PermissionSetLine.objects.filter(application_object=stale).update(
                application_object=existing_by_id,
            )
        stale.delete()

    obj, created = Objects.objects.update_or_create(
        object_id=page.object_id,
        defaults={
            **defaults,
            'object_name': _unique_page_object_name(page),
        },
    )
    return obj, created


def _infer_module(page: 'Page') -> str:
    """Best-effort module code when the page is not in BC_PAGE_REGISTRY."""
    table = (page.source_table or '').lower()
    if table in ('customer', 'salesorder', 'salesinvoice', 'salesorderline', 'salesinvoiceline'):
        return 'sales'
    if table in ('vendor', 'purchaseinvoice', 'purchaseinvoiceline'):
        return 'purchases'
    if table in ('item', 'itemjournal', 'itemledgerentry'):
        return 'inventory'
    if table in ('g_laccount', 'glaccount'):
        return 'financials'
    if table in ('bankaccount', 'bankaccountledgerentry'):
        return 'bankAccount'
    if table in ('expense',):
        return 'expenses'
    if table in ('paymentjournal', 'paymentline', 'paymentmethod'):
        return 'payments'
    return 'general'


@transaction.atomic
def sync_all_page_permission_objects(
    *,
    only_with_object_id: bool = True,
) -> dict[str, int]:
    """Sync every page-engine page that has a BC-style object_id assigned."""
    from pages.models import Page

    stats = {'created': 0, 'updated': 0, 'skipped': 0}

    qs = Page.objects.all().order_by('object_id', 'page_id')
    if only_with_object_id:
        qs = qs.exclude(object_id__isnull=True)

    for page in qs:
        if page.object_id is None:
            stats['skipped'] += 1
            continue
        _, created = sync_page_permission_object(page)
        if created:
            stats['created'] += 1
        else:
            stats['updated'] += 1

    return stats


def apply_object_id_from_registry(page: 'Page') -> 'Page':
    """
    Set ``page.object_id`` from BC or Zentro custom registry when the page name is mapped.

    Clears stale ``object_id`` values on other pages that incorrectly hold the target ID
    (e.g. after registry remaps) so the unique constraint is never violated.
    """
    from pages.bc_page_ids import resolve_page_object_id
    from pages.models import Page

    oid = resolve_page_object_id(page.name)
    if oid is None:
        return page

    for stale in Page.objects.filter(object_id=oid).exclude(page_id=page.page_id):
        if resolve_page_object_id(stale.name) != oid:
            stale.object_id = None
            stale.save(update_fields=['object_id'])

    if page.object_id != oid:
        page.object_id = oid
        page.save(update_fields=['object_id'])
    return page
