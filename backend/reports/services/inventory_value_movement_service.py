from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.db import models
from django.db.models import (
    Case,
    CharField,
    Count,
    DecimalField,
    FloatField,
    IntegerField,
    Min,
    Q,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Cast, Coalesce, TruncDate, TruncMonth

from items.models import ValueEntry

from .base_report_service import BaseReportService

TOP_ITEMS_PER_BUCKET = 20

ENTRY_TYPE_LABELS = {
    "Purchase": "Purchase",
    "Purchase Return": "Purchase Return",
    "Sales": "Sales (COGS)",
    "PositiveAdjustment": "Positive Adjustment",
    "NegativeAdjustment": "Negative Adjustment",
    "DirectCost": "Cost of Goods Sold",
    "Consumption": "Consumption",
    "Output": "Output (Production)",
}

ENTRY_TYPE_CATEGORY = {
    "Purchase": "Stock In",
    "Sales": "Stock Out",
    "PositiveAdjustment": "Stock In",
    "NegativeAdjustment": "Stock Out",
    "DirectCost": "Stock Out",
    "Direct Cost": "Stock Out",
    "Consumption": "Stock Out",
    "Output": "Stock In",
    "Purchase Return": "Stock Out",
}

DETAIL_SECTION_ORDER = [
    "Sales",
    "Purchase",
    "Purchase Return",
    "PositiveAdjustment",
    "NegativeAdjustment",
    "Consumption",
    "Output",
    "DirectCost",
]

GL_SOURCE_BUCKETS = {
    "purchase": ("Purchase", "Stock In"),
    "cogs": ("Cost of Goods Sold", "Stock Out"),
    "positive_adjustment": ("Positive Adjustment", "Stock In"),
    "negative_adjustment": ("Negative Adjustment", "Stock Out"),
    "other_in": ("Other (in)", "Stock In"),
    "other_out": ("Other (out)", "Stock Out"),
}

GL_STOCK_IN_BUCKET_ORDER = ("purchase", "positive_adjustment", "other_in")
GL_STOCK_OUT_BUCKET_ORDER = ("cogs", "negative_adjustment", "other_out")

FORMULA_GUIDE_ENTRY_TYPES = [
    ("Purchase", "Stock In", "Inventory received from supplier — increases stock value"),
    (
        "Sales (COGS)",
        "Stock Out",
        "Cost of goods delivered to customer — reduces stock value",
    ),
    (
        "Positive Adjustment",
        "Stock In",
        "Manual upward correction (e.g. stock count gain)",
    ),
    (
        "Negative Adjustment",
        "Stock Out",
        "Manual downward correction (e.g. spoilage, write-off)",
    ),
    ("Consumption", "Stock Out", "Raw materials consumed in production"),
    ("Output (Production)", "Stock In", "Finished goods produced, added to stock"),
    (
        "Cost of Goods Sold",
        "Stock Out",
        "Cost of goods sold when inventory is delivered to customers — reduces stock value",
    ),
]


class InventoryValueMovementService(BaseReportService):
    """Service for inventory value movement over a period."""

    CACHE_TTL = 600  # 10 minutes

    @staticmethod
    def parse_request_params(request):
        """Parse query params shared by JSON and export endpoints."""
        from datetime import date as date_cls

        period_type = request.query_params.get("period_type", "daily")
        start_date_str = request.query_params.get("start_date")
        end_date_str = request.query_params.get("end_date")
        today = date_cls.today()

        if period_type == "monthly":
            start_date = BaseReportService.parse_date(
                start_date_str, default=today.replace(day=1)
            )
            end_date = BaseReportService.parse_date(end_date_str, default=today)
        else:
            start_date = BaseReportService.parse_date(start_date_str, default=today)
            end_date = BaseReportService.parse_date(end_date_str, default=today)

        if start_date > end_date:
            raise ValueError("start_date cannot be after end_date")

        InventoryValueMovementService._validate_period_type(period_type)
        return start_date, end_date, period_type

    @staticmethod
    def is_all_time_request(request) -> bool:
        return request.query_params.get("all_time", "").lower() in (
            "1",
            "true",
            "yes",
        )

    def resolve_all_time_dates(self, branch=None) -> tuple[date, date]:
        """First inventory posting through today (G/L 2110 and ValueEntry)."""
        from datetime import date as date_cls

        from financials.models import GeneralLedgerEntry

        today = date_cls.today()
        candidates: list[date] = []

        account = self._resolve_resale_items_gl_account()
        if account:
            gl_qs = GeneralLedgerEntry.objects.filter(
                gl_account=account, reversed=False
            )
            if branch is not None:
                gl_qs = gl_qs.filter(global_dimension_1=branch)
            min_gl = gl_qs.aggregate(m=Min("posting_date"))["m"]
            if min_gl:
                candidates.append(min_gl)

        ve_qs = ValueEntry.objects.filter(reversed=False)
        if branch is not None:
            ve_qs = ve_qs.filter(global_dimension_1=branch)
        min_ve = ve_qs.aggregate(m=Min("posting_date"))["m"]
        if min_ve:
            candidates.append(min_ve)

        start_date = min(candidates) if candidates else today.replace(day=1)
        return start_date, today

    @classmethod
    def parse_report_window(cls, request, branch=None) -> tuple[date, date, str]:
        """Parse query params; expand all_time to full inventory history (monthly buckets)."""
        start_date, end_date, period_type = cls.parse_request_params(request)
        if cls.is_all_time_request(request):
            service = cls()
            start_date, end_date = service.resolve_all_time_dates(branch)
            period_type = "monthly"
        return start_date, end_date, period_type

    @staticmethod
    def _to_decimal(value) -> Decimal:
        if value is None:
            return Decimal("0")
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))

    @staticmethod
    def _validate_period_type(period_type: str) -> str:
        valid = {"daily", "monthly", "custom"}
        if period_type not in valid:
            raise ValueError("Invalid period_type. Expected one of: daily, monthly, custom")
        return period_type

    @staticmethod
    def _bucket_key(bucket_value) -> str:
        if hasattr(bucket_value, "isoformat"):
            return bucket_value.isoformat()
        return str(bucket_value)

    @staticmethod
    def _parse_amount_field(value) -> float:
        if value is None or value == "":
            return 0.0
        try:
            return float(str(value).strip().replace(",", ""))
        except (TypeError, ValueError):
            return 0.0

    @classmethod
    def _value_entry_cost_abs(cls, cost_amount) -> Decimal:
        return abs(Decimal(str(cls._parse_amount_field(cost_amount))))

    @classmethod
    def _sum_value_entries_by_category(cls, queryset) -> tuple[Decimal, Decimal]:
        """Sum |cost_amount| into stock in/out using ENTRY_TYPE_CATEGORY (not qty sign)."""
        from items.value_entry_posting import resolve_inventory_entry_type

        inbound = Decimal("0")
        outbound = Decimal("0")
        for ve in queryset.only("entry_type", "document_type", "cost_amount").iterator():
            amount = cls._value_entry_cost_abs(ve.cost_amount)
            if amount == 0:
                continue
            effective = resolve_inventory_entry_type(
                ve.entry_type, ve.document_type
            )
            if cls._entry_type_category(effective or "") == "Stock In":
                inbound += amount
            else:
                outbound += amount
        return inbound, outbound

    @classmethod
    def _entry_type_label(cls, entry_type: str) -> str:
        return ENTRY_TYPE_LABELS.get(entry_type, entry_type or "Unknown")

    @classmethod
    def _entry_type_category(cls, entry_type: str) -> str:
        return ENTRY_TYPE_CATEGORY.get(entry_type, "Stock Out")

    @classmethod
    def _effective_entry_type(cls, entry_type: str, document_type: str | None = None) -> str:
        from items.value_entry_posting import resolve_inventory_entry_type

        return resolve_inventory_entry_type(entry_type, document_type) or entry_type or ""

    @staticmethod
    def _format_period_label(period_key: str, period_type: str) -> str:
        if period_type == "monthly" and len(period_key) >= 7:
            try:
                year, month = period_key[:7].split("-")
                from datetime import date as date_cls

                d = date_cls(int(year), int(month), 1)
                return d.strftime("%b %Y")
            except (ValueError, TypeError):
                pass
        try:
            from datetime import date as date_cls

            parts = period_key.split("-")
            if len(parts) == 3:
                d = date_cls(int(parts[0]), int(parts[1]), int(parts[2]))
                return d.strftime("%d %b %Y")
        except (ValueError, TypeError):
            pass
        return period_key

    @staticmethod
    def _resolve_resale_items_gl_account():
        """Same account resolution as Sales dashboard stock_value."""
        from financials.models import G_LAccount

        return (
            G_LAccount.objects.filter(no="2110", name__icontains="Resale Items").first()
            or G_LAccount.objects.filter(no="2110").first()
            or G_LAccount.objects.filter(name__icontains="Resale Items").first()
        )

    @staticmethod
    def _branch_gl_query(branch):
        """Match branch on global_dimension_1 and dimension_set (BC-style)."""
        from django.db.models import Exists, OuterRef, Q

        from dimension.models import DimensionSetEntry
        from financials.models import GeneralLedgerSetup

        if branch is None:
            return Q()

        branch_id = getattr(branch, "id", branch)
        branch_q = Q(global_dimension_1_id=branch_id)

        gl_setup = GeneralLedgerSetup.objects.first()
        if gl_setup and gl_setup.global_dimension_1_id:
            branch_q |= Q(
                Exists(
                    DimensionSetEntry.objects.filter(
                        dimension_set_id=OuterRef("dimension_set_id"),
                        dimension_code_id=gl_setup.global_dimension_1_id,
                        dimension_value_id=branch_id,
                    )
                )
            )
            branch_code = getattr(branch, "code", None)
            if branch_code:
                branch_q |= Q(
                    global_dimension_1__code=branch_code,
                    global_dimension_1__dimension_code_id=gl_setup.global_dimension_1_id,
                )
        return branch_q

    @staticmethod
    def _gl_active_queryset(qs):
        """Exclude reversed G/L lines (aligns with ValueEntry report totals)."""
        return qs.filter(reversed=False)

    @staticmethod
    def get_sales_dashboard_stock_balance(branch, as_of: date | None = None) -> float:
        """
        G/L 2110 balance using the same filter as SalesDashboardViewSet.stock_value.
        branch=None → organisation-wide (all branches).
        """
        from financials.models import GeneralLedgerEntry

        account = InventoryValueMovementService._resolve_resale_items_gl_account()
        if not account:
            return 0.0

        filt = {"gl_account": account, "reversed": False}
        if as_of is not None:
            filt["posting_date__lte"] = as_of
        if branch is not None:
            filt["global_dimension_1_id"] = getattr(branch, "id", branch)

        total = (
            GeneralLedgerEntry.objects.filter(**filt).aggregate(total=Sum("amount"))[
                "total"
            ]
            or 0.0
        )
        return float(round(total, 2))

    @staticmethod
    def get_gl_resale_items_balances(branch, start_date: date, end_date: date) -> dict:
        """
        G/L account 2110 (Resale Items) balances for reconciliation with ValueEntry totals.
        Uses the same source as the Sales dashboard stock value card.
        """
        from financials.models import GeneralLedgerEntry

        account = InventoryValueMovementService._resolve_resale_items_gl_account()
        if not account:
            return {"available": False}

        def _sum_balance(extra_filter: dict, *, apply_branch: bool) -> float:
            qs = GeneralLedgerEntry.objects.filter(
                gl_account=account, reversed=False, **extra_filter
            )
            if branch is not None and apply_branch:
                qs = qs.filter(
                    InventoryValueMovementService._branch_gl_query(branch)
                )
            total = qs.aggregate(total=Sum("amount"))["total"] or 0.0
            return float(round(total, 2))

        opening_as_of = start_date - timedelta(days=1)
        opening_branch = _sum_balance({"posting_date__lte": opening_as_of}, apply_branch=True)
        closing_branch = _sum_balance({"posting_date__lte": end_date}, apply_branch=True)
        dashboard_branch = _sum_balance({}, apply_branch=True)

        opening_all = _sum_balance({"posting_date__lte": opening_as_of}, apply_branch=False)
        closing_all = _sum_balance({"posting_date__lte": end_date}, apply_branch=False)
        dashboard_all = _sum_balance({}, apply_branch=False)

        branch_gl_untagged = (
            branch is not None
            and dashboard_branch == 0
            and dashboard_all != 0
        )

        def _effective(branch_amt: float, all_amt: float) -> float:
            if branch is None:
                return all_amt
            if branch_amt != 0 or all_amt == 0:
                return branch_amt
            return all_amt

        return {
            "available": True,
            "account_no": account.no,
            "account_name": account.name,
            "opening_balance": _effective(opening_branch, opening_all),
            "closing_balance": _effective(closing_branch, closing_all),
            "dashboard_balance": _effective(dashboard_branch, dashboard_all),
            "opening_balance_branch": opening_branch,
            "closing_balance_branch": closing_branch,
            "dashboard_balance_branch": dashboard_branch,
            "opening_balance_all_branches": opening_all,
            "closing_balance_all_branches": closing_all,
            "dashboard_balance_all_branches": dashboard_all,
            "branch_gl_untagged": branch_gl_untagged,
            "opening_as_of": opening_as_of.isoformat(),
            "closing_as_of": end_date.isoformat(),
        }

    @staticmethod
    def _resolve_gl_queryset(branch):
        """GL queryset for 2110; falls back to all branches when branch lines are untagged."""
        from financials.models import GeneralLedgerEntry

        account = InventoryValueMovementService._resolve_resale_items_gl_account()
        if not account:
            return None, None, False

        def _filtered(apply_branch: bool):
            qs = GeneralLedgerEntry.objects.filter(
                gl_account=account, reversed=False
            )
            if branch is not None and apply_branch:
                qs = qs.filter(InventoryValueMovementService._branch_gl_query(branch))
            return qs

        qs_branch = _filtered(True)
        if branch is not None:
            has_company_entries = GeneralLedgerEntry.objects.filter(
                gl_account=account, reversed=False
            ).exists()
            if has_company_entries and not qs_branch.exists():
                return account, _filtered(False), True
        return account, qs_branch, False

    @staticmethod
    def _gl_balance_as_of(gl_qs, as_of: date) -> Decimal:
        total = gl_qs.filter(posting_date__lte=as_of).aggregate(
            total=Sum("amount")
        )["total"]
        return InventoryValueMovementService._to_decimal(total)

    def _build_gl_movement(
        self,
        start_date: date,
        end_date: date,
        period_type: str,
        branch=None,
    ) -> dict | None:
        """Opening/closing and period buckets from G/L 2110 (Resale Items)."""
        account, gl_qs, branch_gl_untagged = self._resolve_gl_queryset(branch)
        if not account or gl_qs is None:
            return None

        opening_as_of = start_date - timedelta(days=1)
        opening_value = self._gl_balance_as_of(gl_qs, opening_as_of)

        if period_type == "monthly":
            bucket_expression = TruncMonth("posting_date")
        else:
            bucket_expression = TruncDate("posting_date")

        inbound_filter = Q(amount__gt=0)
        outbound_filter = Q(amount__lt=0)
        period_qs = gl_qs.filter(posting_date__range=[start_date, end_date])

        bucket_rows = (
            period_qs.annotate(bucket=bucket_expression)
            .values("bucket")
            .annotate(
                inbound_value=Coalesce(
                    Sum("amount", filter=inbound_filter, output_field=FloatField()),
                    Value(0.0, output_field=FloatField()),
                    output_field=FloatField(),
                ),
                outbound_value=Coalesce(
                    Sum("amount", filter=outbound_filter, output_field=FloatField()),
                    Value(0.0, output_field=FloatField()),
                    output_field=FloatField(),
                ),
            )
            .order_by("bucket")
        )

        buckets = []
        running = opening_value
        total_inbound = Decimal("0")
        total_outbound = Decimal("0")

        for row in bucket_rows:
            inbound = self._to_decimal(row["inbound_value"])
            outbound = abs(self._to_decimal(row["outbound_value"]))
            net = inbound - outbound
            total_inbound += inbound
            total_outbound += outbound
            buckets.append(
                {
                    "period": self._bucket_key(row["bucket"]),
                    "opening_value": float(round(running, 2)),
                    "inbound_value": float(round(inbound, 2)),
                    "outbound_value": float(round(outbound, 2)),
                    "net_change": float(round(net, 2)),
                }
            )
            running += net
            buckets[-1]["closing_value"] = float(round(running, 2))

        net_change = total_inbound - total_outbound
        closing_value = (
            Decimal(str(buckets[-1]["closing_value"]))
            if buckets
            else opening_value + net_change
        )

        return {
            "account_no": account.no,
            "account_name": account.name,
            "branch_gl_untagged": branch_gl_untagged,
            "opening_as_of": opening_as_of.isoformat(),
            "closing_as_of": end_date.isoformat(),
            "summary": {
                "opening_value": float(round(opening_value, 2)),
                "inbound_value": float(round(total_inbound, 2)),
                "outbound_value": float(round(total_outbound, 2)),
                "net_change": float(round(net_change, 2)),
                "closing_value": float(round(closing_value, 2)),
            },
            "buckets": buckets,
        }

    @staticmethod
    def _gl_source_bucket_case():
        """Classify 2110 lines for period breakdown (matches how postings are created)."""
        return Case(
            When(general_posting_type="Purchase", then=Value("purchase")),
            When(general_posting_type="Sales", then=Value("cogs")),
            When(
                description__icontains="Positive Adjustment",
                then=Value("positive_adjustment"),
            ),
            When(
                description__icontains="Negative Adjustment",
                then=Value("negative_adjustment"),
            ),
            default=Value("other"),
            output_field=CharField(),
        )

    def _compute_gl_period_breakdown(
        self, start_date: date, end_date: date, branch=None
    ) -> tuple[list, list]:
        """Stock in/out subtotals from G/L 2110 — aligns with headline metric cards."""
        account, gl_qs, _ = self._resolve_gl_queryset(branch)
        if not account or gl_qs is None:
            return [], []

        period_qs = gl_qs.filter(posting_date__range=[start_date, end_date])
        inbound_filter = Q(amount__gt=0)
        outbound_filter = Q(amount__lt=0)

        rows = (
            period_qs.annotate(source_bucket=self._gl_source_bucket_case())
            .values("source_bucket")
            .annotate(
                transaction_count=Count("id"),
                inbound_value=Coalesce(
                    Sum("amount", filter=inbound_filter, output_field=FloatField()),
                    Value(0.0, output_field=FloatField()),
                    output_field=FloatField(),
                ),
                outbound_value=Coalesce(
                    Sum("amount", filter=outbound_filter, output_field=FloatField()),
                    Value(0.0, output_field=FloatField()),
                    output_field=FloatField(),
                ),
            )
        )

        by_bucket: dict[str, dict] = {}
        for row in rows:
            bucket = row["source_bucket"] or "other"
            inbound = float(round(self._to_decimal(row["inbound_value"]), 2))
            outbound = float(round(abs(self._to_decimal(row["outbound_value"])), 2))
            if inbound <= 0 and outbound <= 0:
                continue

            if bucket == "other":
                if inbound > 0:
                    self._merge_gl_bucket(by_bucket, "other_in", inbound, row["transaction_count"])
                if outbound > 0:
                    self._merge_gl_bucket(
                        by_bucket, "other_out", outbound, row["transaction_count"]
                    )
                continue

            label, direction = GL_SOURCE_BUCKETS.get(
                bucket, ("Other", "Stock In" if inbound > outbound else "Stock Out")
            )
            if direction == "Stock In" and inbound > 0:
                self._merge_gl_bucket(by_bucket, bucket, inbound, row["transaction_count"])
            elif direction == "Stock Out" and outbound > 0:
                self._merge_gl_bucket(by_bucket, bucket, outbound, row["transaction_count"])
            elif inbound > 0:
                self._merge_gl_bucket(by_bucket, "other_in", inbound, row["transaction_count"])
            elif outbound > 0:
                self._merge_gl_bucket(
                    by_bucket, "other_out", outbound, row["transaction_count"]
                )

        stock_in_lines = []
        for key in GL_STOCK_IN_BUCKET_ORDER:
            if key in by_bucket:
                label = GL_SOURCE_BUCKETS[key][0]
                stock_in_lines.append(
                    {
                        "entry_type": key,
                        "label": label,
                        "amount": by_bucket[key]["amount"],
                        "transaction_count": by_bucket[key]["transaction_count"],
                    }
                )

        stock_out_lines = []
        for key in GL_STOCK_OUT_BUCKET_ORDER:
            if key in by_bucket:
                label = GL_SOURCE_BUCKETS[key][0]
                stock_out_lines.append(
                    {
                        "entry_type": key,
                        "label": label,
                        "amount": by_bucket[key]["amount"],
                        "transaction_count": by_bucket[key]["transaction_count"],
                    }
                )

        return stock_in_lines, stock_out_lines

    @staticmethod
    def _merge_gl_bucket(by_bucket: dict, key: str, amount: float, transaction_count: int):
        existing = by_bucket.get(key)
        if existing:
            existing["amount"] = float(round(existing["amount"] + amount, 2))
            existing["transaction_count"] += transaction_count
        else:
            by_bucket[key] = {
                "amount": amount,
                "transaction_count": transaction_count,
            }

    def _compute_value_entry_totals(
        self,
        start_date: date,
        end_date: date,
        branch=None,
    ) -> dict:
        """ValueEntry totals for G/L comparison — uses entry-type category, not qty sign."""
        period_qs = ValueEntry.objects.filter(
            posting_date__range=[start_date, end_date],
            reversed=False,
        )
        if branch:
            period_qs = period_qs.filter(global_dimension_1=branch)

        total_inbound, total_outbound = self._sum_value_entries_by_category(period_qs)

        opening_qs = ValueEntry.objects.filter(
            posting_date__lt=start_date,
            reversed=False,
        )
        if branch:
            opening_qs = opening_qs.filter(global_dimension_1=branch)

        opening_inbound, opening_outbound = self._sum_value_entries_by_category(
            opening_qs
        )
        opening_value = opening_inbound - opening_outbound
        net_change = total_inbound - total_outbound
        closing_value = opening_value + net_change

        return {
            "opening_value": float(round(opening_value, 2)),
            "inbound_value": float(round(total_inbound, 2)),
            "outbound_value": float(round(total_outbound, 2)),
            "net_change": float(round(net_change, 2)),
            "closing_value": float(round(closing_value, 2)),
        }

    def _compute_movement_by_entry_type(
        self, start_date: date, end_date: date, branch=None
    ) -> list:
        """ValueEntry totals in the period grouped by entry type (sales, purchase, etc.).

        Stock in/out per type follows ENTRY_TYPE_CATEGORY (e.g. negative adjustments
        are always stock out), not item_ledger_entry_quantity sign — some postings
        store positive quantities on outbound entry types.
        """
        queryset = ValueEntry.objects.filter(
            posting_date__range=[start_date, end_date],
            reversed=False,
        )
        if branch:
            queryset = queryset.filter(global_dimension_1=branch)

        grouped: dict[str, dict] = defaultdict(
            lambda: {"cost": Decimal("0"), "revenue": Decimal("0"), "count": 0}
        )
        for ve in queryset.only(
            "entry_type", "document_type", "cost_amount", "sales_amount"
        ).iterator():
            entry_type = self._effective_entry_type(
                ve.entry_type or "", ve.document_type
            )
            bucket = grouped[entry_type]
            bucket["cost"] += self._value_entry_cost_abs(ve.cost_amount)
            bucket["revenue"] += Decimal(str(self._parse_amount_field(ve.sales_amount)))
            bucket["count"] += 1

        movement_by_entry_type = []
        for entry_type, data in grouped.items():
            category = self._entry_type_category(entry_type)
            total = float(round(data["cost"], 2))
            if total == 0:
                continue
            stock_in = total if category == "Stock In" else 0.0
            stock_out = total if category == "Stock Out" else 0.0
            movement_by_entry_type.append(
                {
                    "entry_type": entry_type,
                    "entry_type_label": self._entry_type_label(entry_type),
                    "category": category,
                    "transaction_count": data["count"],
                    "stock_in_value": stock_in,
                    "stock_out_value": stock_out,
                    "net_value": float(round(stock_in - stock_out, 2)),
                    "sales_revenue": float(round(data["revenue"], 2)),
                }
            )
        movement_by_entry_type.sort(
            key=lambda r: r["stock_in_value"] + r["stock_out_value"],
            reverse=True,
        )
        return movement_by_entry_type

    @staticmethod
    def _breakdown_lines_from_entry_types(
        movement_by_entry_type: list, *, direction: str
    ) -> list:
        """direction: 'in' | 'out' — only entry types in the matching category."""
        expected_category = "Stock In" if direction == "in" else "Stock Out"
        key = "stock_in_value" if direction == "in" else "stock_out_value"
        lines = []
        for row in movement_by_entry_type:
            if row.get("category") and row.get("category") != expected_category:
                continue
            amount = float(row.get(key, 0))
            if amount <= 0:
                continue
            lines.append(
                {
                    "entry_type": row.get("entry_type", ""),
                    "label": row.get("entry_type_label", ""),
                    "amount": amount,
                    "transaction_count": row.get("transaction_count", 0),
                }
            )
        return lines

    def _attach_value_entry_reconciliation(
        self,
        summary: dict,
        branch,
        start_date: date,
        end_date: date,
        movement_by_entry_type: list | None = None,
    ) -> None:
        ve = self._compute_value_entry_totals(start_date, end_date, branch)
        if movement_by_entry_type is None:
            movement_by_entry_type = self._compute_movement_by_entry_type(
                start_date, end_date, branch
            )
        opening_gl = summary.get("opening_value", 0)
        closing_gl = summary.get("closing_value", 0)

        summary["value_entry_reconciliation"] = {
            "available": True,
            "opening_balance": ve["opening_value"],
            "closing_balance": ve["closing_value"],
            "inbound_balance": ve["inbound_value"],
            "outbound_balance": ve["outbound_value"],
            "opening_variance": float(round(opening_gl - ve["opening_value"], 2)),
            "closing_variance": float(round(closing_gl - ve["closing_value"], 2)),
            "period_inbound_variance": float(
                round(summary.get("inbound_value", 0) - ve["inbound_value"], 2)
            ),
            "period_outbound_variance": float(
                round(summary.get("outbound_value", 0) - ve["outbound_value"], 2)
            ),
            "ve_stock_in_breakdown": self._breakdown_lines_from_entry_types(
                movement_by_entry_type, direction="in"
            ),
            "ve_stock_out_breakdown": self._breakdown_lines_from_entry_types(
                movement_by_entry_type, direction="out"
            ),
        }

    @staticmethod
    def _coalesce_decimal(sum_expr, amount_field: DecimalField):
        return Coalesce(
            sum_expr,
            Value(Decimal("0"), output_field=amount_field),
            output_field=amount_field,
        )

    @staticmethod
    def _coalesce_integer(sum_expr):
        int_field = IntegerField()
        return Coalesce(
            sum_expr,
            Value(0, output_field=int_field),
            output_field=int_field,
        )

    def _attach_item_breakdowns(self, queryset, bucket_expression, buckets: list) -> None:
        """Attach top items per bucket from a single grouped query."""
        amount_field = DecimalField(max_digits=18, decimal_places=2)
        value_expression = Cast("cost_amount", amount_field)
        inbound_filter = models.Q(item_ledger_entry_quantity__gt=0)
        outbound_filter = models.Q(item_ledger_entry_quantity__lt=0)

        item_rows = (
            queryset.annotate(bucket=bucket_expression)
            .values("bucket", "item__no", "item__item_name")
            .annotate(
                inbound_value=self._coalesce_decimal(
                    Sum(value_expression, filter=inbound_filter),
                    amount_field,
                ),
                outbound_value=self._coalesce_decimal(
                    Sum(value_expression, filter=outbound_filter),
                    amount_field,
                ),
                net_qty=self._coalesce_integer(Sum("item_ledger_entry_quantity")),
            )
        )

        grouped: dict[str, list] = defaultdict(list)
        for row in item_rows:
            key = self._bucket_key(row["bucket"])
            inbound = float(round(self._to_decimal(row["inbound_value"]), 2))
            outbound = float(round(abs(self._to_decimal(row["outbound_value"])), 2))
            net_qty = float(round(self._to_decimal(row["net_qty"]), 4))
            if inbound == 0 and outbound == 0 and net_qty == 0:
                continue
            grouped[key].append(
                {
                    "item_no": row["item__no"] or "",
                    "item_description": row["item__item_name"] or "",
                    "inbound_value": inbound,
                    "outbound_value": outbound,
                    "net_qty": net_qty,
                    "_sort": inbound + outbound,
                }
            )

        bucket_map = {b["period"]: b for b in buckets}
        for period_key, items in grouped.items():
            items.sort(key=lambda x: x["_sort"], reverse=True)
            top = items[:TOP_ITEMS_PER_BUCKET]
            for item in top:
                item.pop("_sort", None)
            if period_key in bucket_map:
                bucket_map[period_key]["items"] = top
            else:
                # Bucket exists only in item query (edge case)
                pass

        for bucket in buckets:
            bucket.setdefault("items", [])

    def generate_report(
        self,
        start_date: date,
        end_date: date,
        period_type: str = "daily",
        branch=None,
    ) -> dict:
        self.start_timer()
        self._validate_period_type(period_type)
        self.validate_filters({"start_date": start_date, "end_date": end_date})

        gl_movement = self._build_gl_movement(
            start_date, end_date, period_type, branch=branch
        )
        branch_gl_untagged = False
        valuation_source = "gl"

        movement_by_entry_type = self._compute_movement_by_entry_type(
            start_date, end_date, branch
        )

        if gl_movement:
            summary = gl_movement["summary"]
            buckets = gl_movement["buckets"]
            summary["valuation_source"] = valuation_source
            summary["gl_account_no"] = gl_movement["account_no"]
            summary["gl_account_name"] = gl_movement["account_name"]
            branch_gl_untagged = gl_movement["branch_gl_untagged"]
            stock_in_bd, stock_out_bd = self._compute_gl_period_breakdown(
                start_date, end_date, branch
            )
            summary["stock_in_breakdown"] = stock_in_bd
            summary["stock_out_breakdown"] = stock_out_bd
            self._attach_value_entry_reconciliation(
                summary,
                branch,
                start_date,
                end_date,
                movement_by_entry_type=movement_by_entry_type,
            )
        else:
            valuation_source = "value_entry"
            ve = self._compute_value_entry_totals(start_date, end_date, branch)
            summary = {**ve, "valuation_source": valuation_source}
            buckets = []

        amount_field = DecimalField(max_digits=18, decimal_places=2)
        ve_queryset = ValueEntry.objects.filter(
            posting_date__range=[start_date, end_date],
            reversed=False,
        )
        if branch:
            ve_queryset = ve_queryset.filter(global_dimension_1=branch)
        if period_type == "monthly":
            bucket_expression = TruncMonth("posting_date")
        else:
            bucket_expression = TruncDate("posting_date")
        self._attach_item_breakdowns(ve_queryset, bucket_expression, buckets)

        report_data = {
            "summary": summary,
            "buckets": buckets,
            "movement_by_entry_type": movement_by_entry_type,
            "filters": {
                "period_type": period_type,
                "valuation_source": valuation_source,
                "branch_gl_untagged": branch_gl_untagged,
            },
        }

        return self.format_response(
            report_type="inventory_value_movement",
            data=report_data,
            period={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "period_type": period_type,
            },
            cached=False,
        )

    def build_export_details(
        self,
        start_date: date,
        end_date: date,
        period_type: str,
        opening_value: float,
        buckets: list,
        branch=None,
    ) -> dict:
        """Export-only detail: entry-type summary, grouped ledger, sales detail."""
        self._validate_period_type(period_type)
        amount_field = DecimalField(max_digits=18, decimal_places=2)
        cost_expr = Cast("cost_amount", amount_field)
        revenue_expr = Cast("sales_amount", amount_field)
        inbound_filter = models.Q(item_ledger_entry_quantity__gt=0)
        outbound_filter = models.Q(item_ledger_entry_quantity__lt=0)

        queryset = ValueEntry.objects.filter(
            posting_date__range=[start_date, end_date],
            reversed=False,
        )
        if branch:
            queryset = queryset.filter(global_dimension_1=branch)

        if period_type == "monthly":
            bucket_expression = TruncMonth("posting_date")
        else:
            bucket_expression = TruncDate("posting_date")

        movement_by_entry_type = self._compute_movement_by_entry_type(
            start_date, end_date, branch
        )

        bucket_map = {b["period"]: b for b in buckets}
        ledger_entries = (
            queryset.select_related("item", "global_dimension_1")
            .annotate(period_bucket=bucket_expression)
            .order_by("posting_date", "id")
        )

        all_transactions = []
        for entry in ledger_entries:
            qty = entry.item_ledger_entry_quantity or 0
            cost = self._parse_amount_field(entry.cost_amount)
            revenue = self._parse_amount_field(entry.sales_amount)
            entry_type = entry.entry_type or ""
            direction = "Stock In" if qty > 0 else "Stock Out"
            period_key = self._bucket_key(entry.period_bucket)

            all_transactions.append(
                {
                    "period": period_key,
                    "posting_date": entry.posting_date.isoformat(),
                    "document_no": entry.document_no or "",
                    "entry_type": entry_type,
                    "entry_type_label": self._entry_type_label(entry_type),
                    "document_type": entry.document_type or "",
                    "item_no": entry.item.no if entry.item else "",
                    "item_description": entry.item.item_name if entry.item else "",
                    "quantity": qty,
                    "direction": direction,
                    "cost_amount": round(cost, 2),
                    "sales_amount": round(revenue, 2),
                    "revenue": round(revenue, 2) if entry_type == "Sales" else 0.0,
                    "description": (entry.description or "")[:200],
                }
            )

        running_balance = float(opening_value)
        for txn in all_transactions:
            if txn["direction"] == "Stock In":
                running_balance += txn["cost_amount"]
            else:
                running_balance -= txn["cost_amount"]
            txn["running_balance"] = round(running_balance, 2)

        grouped_txns: dict[str, list] = defaultdict(list)
        for txn in all_transactions:
            grouped_txns[txn["period"]].append(txn)

        ledger_groups = []
        ordered_periods = [b["period"] for b in buckets] + [
            p for p in sorted(grouped_txns.keys()) if p not in bucket_map
        ]
        seen_periods = set()
        for period_key in ordered_periods:
            if period_key in seen_periods:
                continue
            seen_periods.add(period_key)
            bucket = bucket_map.get(period_key, {})
            ledger_groups.append(
                {
                    "period": period_key,
                    "period_label": self._format_period_label(
                        period_key, period_type
                    ),
                    "opening_value": float(
                        bucket.get("opening_value", opening_value)
                    ),
                    "closing_value": float(
                        bucket.get(
                            "closing_value",
                            opening_value + bucket.get("net_change", 0),
                        )
                    ),
                    "stock_in": float(bucket.get("inbound_value", 0)),
                    "stock_out": float(bucket.get("outbound_value", 0)),
                    "net_change": float(bucket.get("net_change", 0)),
                    "transactions": grouped_txns.get(period_key, []),
                }
            )

        sales_detail = []
        total_cogs = 0.0
        total_revenue = 0.0
        for txn in all_transactions:
            if txn["entry_type"] != "Sales":
                continue
            cogs = txn["cost_amount"]
            revenue = txn["sales_amount"]
            margin = round(revenue - cogs, 2)
            sales_detail.append(
                {
                    "posting_date": txn["posting_date"],
                    "document_no": txn["document_no"],
                    "item_no": txn["item_no"],
                    "item_description": txn["item_description"],
                    "quantity": abs(txn["quantity"]),
                    "cogs": cogs,
                    "revenue": revenue,
                    "gross_margin": margin,
                }
            )
            total_cogs += cogs
            total_revenue += revenue

        sales_totals = {
            "cogs": round(total_cogs, 2),
            "revenue": round(total_revenue, 2),
            "gross_margin": round(total_revenue - total_cogs, 2),
        }

        by_entry_type: dict[str, list] = defaultdict(list)
        for txn in all_transactions:
            by_entry_type[txn["entry_type"]].append(txn)

        detail_sections = []
        seen_types = set()
        for entry_type in DETAIL_SECTION_ORDER:
            rows = by_entry_type.get(entry_type, [])
            if not rows:
                continue
            seen_types.add(entry_type)
            stock_in = sum(
                t["cost_amount"] for t in rows if t["direction"] == "Stock In"
            )
            stock_out = sum(
                t["cost_amount"] for t in rows if t["direction"] == "Stock Out"
            )
            detail_sections.append(
                {
                    "entry_type": entry_type,
                    "title": self._entry_type_label(entry_type),
                    "category": self._entry_type_category(entry_type),
                    "transaction_count": len(rows),
                    "stock_in_total": round(stock_in, 2),
                    "stock_out_total": round(stock_out, 2),
                    "net_cost": round(stock_in - stock_out, 2),
                    "sales_revenue": round(
                        sum(t.get("sales_amount", 0) for t in rows), 2
                    )
                    if entry_type == "Sales"
                    else 0.0,
                    "rows": rows,
                }
            )

        for entry_type in sorted(by_entry_type.keys()):
            if entry_type in seen_types:
                continue
            rows = by_entry_type[entry_type]
            stock_in = sum(
                t["cost_amount"] for t in rows if t["direction"] == "Stock In"
            )
            stock_out = sum(
                t["cost_amount"] for t in rows if t["direction"] == "Stock Out"
            )
            detail_sections.append(
                {
                    "entry_type": entry_type,
                    "title": self._entry_type_label(entry_type),
                    "category": self._entry_type_category(entry_type),
                    "transaction_count": len(rows),
                    "stock_in_total": round(stock_in, 2),
                    "stock_out_total": round(stock_out, 2),
                    "net_cost": round(stock_in - stock_out, 2),
                    "sales_revenue": 0.0,
                    "rows": rows,
                }
            )

        return {
            "movement_by_entry_type": movement_by_entry_type,
            "ledger_groups": ledger_groups,
            "detail_sections": detail_sections,
            "sales_detail": sales_detail,
            "sales_totals": sales_totals,
            "formula_guide_entry_types": FORMULA_GUIDE_ENTRY_TYPES,
            "transaction_count": len(all_transactions),
        }
