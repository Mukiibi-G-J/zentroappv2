"""
Branch filtering utility for multi-branch support.

When General Ledger Setup has enable_multiple_branches=True, filter querysets
by the user's global_dimension_1 (branch) so users only see data from their branch.

The branch can come from:
- X-Branch-Id request header (from frontend selected branch in modal), unless the
  user has can_switch_branch=False (then header is ignored; locked to assigned branch)
- request.user.global_dimension_1 (user's assigned branch in DB)
"""

import logging

from django.db.models import Q

logger = logging.getLogger(__name__)

# Header name for branch ID from frontend (selected branch in branch selection modal)
BRANCH_HEADER = "HTTP_X_BRANCH_ID"
# When set to "all", multi-branch users who may switch branch see combined data (managers).
BRANCH_SCOPE_HEADER = "HTTP_X_BRANCH_SCOPE"
ALL_BRANCH_SCOPE = "all"


def branch_scope_is_all(request):
    """True when client requests org-wide data (only allowed for can_switch_branch users)."""
    if not request:
        return False
    scope = (request.META.get(BRANCH_SCOPE_HEADER) or "").strip().lower()
    if scope != ALL_BRANCH_SCOPE:
        return False
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    try:
        from financials.models import GeneralLedgerSetup

        gl_setup = GeneralLedgerSetup.objects.first()
        if not gl_setup or not getattr(gl_setup, "enable_multiple_branches", False):
            return False
    except Exception:
        return False
    return getattr(user, "can_switch_branch", True)


def get_branch_for_request(request):
    """
    Get the branch (DimensionValue) to use for filtering.
    Prefers X-Branch-Id header (from frontend selection), falls back to user.global_dimension_1.

    When multi-branch is enabled and the user is not allowed to switch branch,
    always returns the user's assigned global_dimension_1 (ignores X-Branch-Id).
    Superusers may always use the header.
    """
    user = getattr(request, "user", None) if request else None
    if user and getattr(user, "is_authenticated", False):
        try:
            from financials.models import GeneralLedgerSetup

            gl_setup = GeneralLedgerSetup.objects.first()
            multi = gl_setup and getattr(gl_setup, "enable_multiple_branches", False)
            if multi and not getattr(user, "is_superuser", False):
                if not getattr(user, "can_switch_branch", True):
                    return getattr(user, "global_dimension_1", None)
        except Exception:
            pass

    branch = None
    branch_id = request.META.get(BRANCH_HEADER) if request else None

    if branch_id:
        try:
            from dimension.models import DimensionValue
            branch = DimensionValue.objects.filter(pk=int(branch_id)).first()
            if not branch:
                logger.warning(
                    "branch_filter: X-Branch-Id=%s not found in DimensionValue (wrong id or tenant?)",
                    branch_id,
                )
        except (ValueError, TypeError) as e:
            logger.warning(
                "branch_filter: X-Branch-Id=%r invalid: %s",
                branch_id,
                e,
            )
    else:
        logger.debug(
            "branch_filter: No X-Branch-Id header, will use user.global_dimension_1"
        )
    if not branch and request and request.user:
        branch = getattr(request.user, "global_dimension_1", None)
    return branch


# Models that filter through a related FK (e.g. header with lines that have dimension)
# Keys use label_lower (app.modelname lowercase)
# NOTE: sales.salesinvoice and purchases.purchaseinvoice use header global_dimension_1 —
# filter by that field directly (below). Do NOT route purchase invoices through lines:
# invoices with no lines yet would disappear from list queries (lines join excludes them).
FILTER_THROUGH_RELATION = {
    "sales.salesorder": "lines",
    "restaurant_management.restaurantorderitem": "order",
    "restaurant_management.restaurantcheck": "order",
    "restaurant_management.orderactionlog": "order",
    "restaurant_management.orderitemmodifier": "order_item__order",
}


def filter_queryset_by_branch(queryset, user, model_class=None, request=None):
    """
    When enable_multiple_branches and user has branch, filter by global_dimension_1_id.
    Returns filtered queryset. Skip if single-branch or no branch.

    Args:
        queryset: Django QuerySet to filter
        user: Request user (must have global_dimension_1 attribute)
        model_class: Optional model class for the queryset (used to check for
                     global_dimension_1 field). If None, infers from queryset.model.
        request: Optional request object - if provided, branch is taken from
                 X-Branch-Id header first, then user.global_dimension_1.

    Returns:
        Filtered queryset
    """
    try:
        from financials.models import GeneralLedgerSetup
    except ImportError:
        return queryset

    gl_setup = GeneralLedgerSetup.objects.first()
    if not gl_setup or not getattr(gl_setup, "enable_multiple_branches", False):
        logger.debug("branch_filter: Skipped - multi-branch disabled or no GL setup")
        return queryset

    if request and branch_scope_is_all(request):
        logger.debug("branch_filter: X-Branch-Scope=all — skipping branch filter")
        return queryset

    # Prefer branch from request header (frontend selection), else user's assigned branch
    branch = None
    if request:
        branch = get_branch_for_request(request)
        if branch:
            logger.debug("branch_filter: branch from X-Branch-Id header: %s", branch.code)
    if not branch:
        branch = getattr(user, "global_dimension_1", None)
        if branch:
            logger.debug("branch_filter: branch from user.global_dimension_1: %s", branch.code)
    if not branch:
        logger.debug("branch_filter: Skipped - no branch (header or user)")
        return queryset

    model = model_class or getattr(queryset, "model", None)
    if not model:
        return queryset

    # model_name is lowercase (e.g. "item"), label_lower is "items.item"
    model_label = model._meta.label_lower
    rel_name = FILTER_THROUGH_RELATION.get(model_label)
    if rel_name:
        return queryset.filter(
            **{f"{rel_name}__global_dimension_1_id": branch.id}
        ).distinct()

    if hasattr(model, "global_dimension_1"):
        return queryset.filter(global_dimension_1_id=branch.id)

    # For models with only dimension_set, filter via DimensionSet entries
    if hasattr(model, "dimension_set"):
        from django.db.models import Exists, OuterRef
        from dimension.models import DimensionSetEntry

        if not gl_setup.global_dimension_1_id:
            return queryset

        dim_set_field = "dimension_set"
        if hasattr(model, "dimension_set_id"):
            subquery = DimensionSetEntry.objects.filter(
                dimension_set_id=OuterRef("dimension_set_id"),
                dimension_code_id=gl_setup.global_dimension_1_id,
                dimension_value_id=branch.id,
            )
            return queryset.filter(Exists(subquery))
        return queryset

    # items.Item: shared across branches (no filter). Branch filtering is on ItemLedgerEntries.
    return queryset


def filter_queryset_by_branch_location(
    queryset, user, request, *, location_lookup="location"
):
    """
    Restrict rows to a branch using Location.code == DimensionValue.code (Zentro POS convention).

    Used for restaurant floors/tables where there is no global_dimension_1 on the model but
    ``items.Location`` is linked to the branch.

    Honors X-Branch-Scope: all the same way as filter_queryset_by_branch.
    """
    try:
        from financials.models import GeneralLedgerSetup
    except ImportError:
        return queryset

    gl_setup = GeneralLedgerSetup.objects.first()
    if not gl_setup or not getattr(gl_setup, "enable_multiple_branches", False):
        return queryset

    if request and branch_scope_is_all(request):
        return queryset

    branch = None
    if request:
        branch = get_branch_for_request(request)
    if not branch:
        branch = getattr(user, "global_dimension_1", None)
    if not branch:
        return queryset

    # Floors created via page setup may omit location until assigned; include those
    # rows so POS and setup lists stay in sync (single-branch and migration cases).
    return queryset.filter(
        Q(**{f"{location_lookup}__code": branch.code})
        | Q(**{f"{location_lookup}__isnull": True})
    )


def filter_reservation_queryset(queryset, user, request):
    """
    Reservations may have no table yet; include those rows for all branches, or scope
    by table.floor.location when a table is assigned.
    """
    try:
        from financials.models import GeneralLedgerSetup
    except ImportError:
        return queryset

    gl_setup = GeneralLedgerSetup.objects.first()
    if not gl_setup or not getattr(gl_setup, "enable_multiple_branches", False):
        return queryset

    if request and branch_scope_is_all(request):
        return queryset

    branch = None
    if request:
        branch = get_branch_for_request(request)
    if not branch:
        branch = getattr(user, "global_dimension_1", None)
    if not branch:
        return queryset

    return queryset.filter(
        Q(table__isnull=True) | Q(table__floor__location__code=branch.code)
    )
