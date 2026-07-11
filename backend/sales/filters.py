from django.contrib import admin
from django.utils.translation import gettext_lazy as _


class BranchListFilter(admin.SimpleListFilter):
    """Filter sales lines by branch (Global Dimension 1).

    Restricts choices to ``DimensionValue`` rows whose ``dimension_code`` matches
    the General Ledger Setup's ``global_dimension_1`` (typically the BRANCH
    dimension). Falls back to the dimension whose code is ``"BRANCH"`` when no
    GL Setup is configured. Filters the queryset on ``global_dimension_1``.
    """

    title = _("Branch")
    parameter_name = "branch"

    def _branch_dimension(self):
        # Resolve which Dimension represents the branch in this tenant.
        try:
            from financials.models import GeneralLedgerSetup
        except Exception:
            GeneralLedgerSetup = None

        gl_setup = GeneralLedgerSetup.objects.first() if GeneralLedgerSetup else None
        if gl_setup and getattr(gl_setup, "global_dimension_1_id", None):
            return gl_setup.global_dimension_1

        from dimension.models import Dimension

        return Dimension.objects.filter(code__iexact="BRANCH").first()

    def lookups(self, request, model_admin):
        from dimension.models import DimensionValue

        branch_dim = self._branch_dimension()
        qs = DimensionValue.objects.all()
        if branch_dim is not None:
            qs = qs.filter(dimension_code=branch_dim)
        qs = qs.order_by("code")
        return [(str(dv.pk), f"{dv.code} — {dv.description}".strip(" —")) for dv in qs]

    def queryset(self, request, queryset):
        value = self.value()
        if not value:
            return queryset
        try:
            dv_id = int(value)
        except (TypeError, ValueError):
            return queryset
        return queryset.filter(global_dimension_1_id=dv_id)


class PostingReadinessFilter(admin.SimpleListFilter):
    title = _("Posting Readiness")
    parameter_name = "posting_readiness"

    def lookups(self, request, model_admin):
        return (
            ("ready", _("Ready to Post")),
            ("insufficient_inventory", _("Insufficient Inventory")),
            ("posted", _("Already Posted")),
            ("error", _("Error Checking")),
        )

    def queryset(self, request, queryset):
        if self.value() == "ready":
            # This would need to be implemented with a custom queryset method
            # For now, we'll return all non-posted invoices
            return queryset.filter(status__in=["Open", "Draft"])
        elif self.value() == "insufficient_inventory":
            # This would need custom logic to check inventory
            return queryset.none()  # Placeholder
        elif self.value() == "posted":
            return queryset.filter(status="Posted")
        elif self.value() == "error":
            return queryset.none()  # Placeholder
        return queryset
