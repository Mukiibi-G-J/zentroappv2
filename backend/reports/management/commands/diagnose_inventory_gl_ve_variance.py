"""
Diagnose G/L 2110 vs ValueEntry variance for the Inventory Value Movement report.

Usage:
  python manage.py tenant_command diagnose_inventory_gl_ve_variance \\
      --schema=<tenant> --branch-code=MWANJARI --start=2026-01-01 --end=2026-05-20

Read-only: no data changes.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Count, Q, Sum

from financials.models import GeneralLedgerEntry
from items.enums import EntryType
from items.models import ItemLedgerEntries, ValueEntry
from reports.services.inventory_value_movement_service import (
    InventoryValueMovementService,
)

try:
    from django_tenants.utils import schema_context
except ImportError:
    schema_context = None


def _parse_date(value: str, default: date) -> date:
    if not value:
        return default
    return datetime.strptime(value, "%Y-%m-%d").date()


def _money(n) -> str:
    return f"{float(n):,.2f}"


class Command(BaseCommand):
    help = (
        "Read-only diagnosis of G/L 2110 vs ValueEntry variance "
        "(inventory value movement reconciliation)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            type=str,
            help="Tenant schema (use with tenant_command).",
        )
        parser.add_argument(
            "--branch-code",
            type=str,
            default="",
            help="Branch DimensionValue code or description fragment (optional).",
        )
        parser.add_argument(
            "--start",
            type=str,
            default="",
            help="Period start YYYY-MM-DD (default: first day of current month).",
        )
        parser.add_argument(
            "--end",
            type=str,
            default="",
            help="Period end YYYY-MM-DD (default: today).",
        )
        parser.add_argument(
            "--sample-docs",
            type=int,
            default=3,
            help="Number of negative-adjustment document_no samples to trace.",
        )

    def handle(self, *args, **options):
        today = date.today()
        start_date = _parse_date(options.get("start"), today.replace(day=1))
        end_date = _parse_date(options.get("end"), today)
        branch_code = (options.get("branch_code") or "").strip()
        sample_docs = max(1, int(options.get("sample_docs") or 3))

        def run():
            from dimension.models import DimensionValue

            branch = None
            if branch_code:
                branch = (
                    DimensionValue.objects.filter(
                        Q(code__iexact=branch_code)
                        | Q(description__icontains=branch_code)
                    )
                    .order_by("id")
                    .first()
                )
                if not branch:
                    self.stdout.write(
                        self.style.ERROR(
                            f"No branch matched --branch-code={branch_code!r}"
                        )
                    )
                    return

            self._print_header(start_date, end_date, branch)
            self._section_report_math(start_date, end_date, branch)
            self._section_negative_adjustment_audit(start_date, end_date, branch)
            self._section_document_tie_out(start_date, end_date, branch, sample_docs)
            self._section_purchase_tie_out(start_date, end_date, branch)
            self._section_opening_variance_audit(start_date, branch)
            self._section_recommendation()

        if schema_context and options.get("schema"):
            with schema_context(options["schema"]):
                run()
        else:
            run()

    def _print_header(self, start_date, end_date, branch):
        self.stdout.write("\n" + "=" * 72)
        self.stdout.write("INVENTORY G/L 2110 vs VALUE ENTRY VARIANCE DIAGNOSIS")
        self.stdout.write("=" * 72)
        self.stdout.write(f"Period: {start_date} to {end_date}")
        if branch:
            self.stdout.write(
                f"Branch: id={branch.id} code={branch.code!r} "
                f"description={branch.description!r}"
            )
        else:
            self.stdout.write("Branch: (all / company-wide G/L fallback may apply)")
        self.stdout.write("")

    def _section_report_math(self, start_date, end_date, branch):
        self.stdout.write(self.style.MIGRATE_HEADING("1) Report reconciliation math"))
        service = InventoryValueMovementService()
        gl_movement = service._build_gl_movement(
            start_date, end_date, "custom", branch=branch
        )
        if not gl_movement:
            self.stdout.write(self.style.ERROR("  G/L 2110 not available for this tenant."))
            return

        summary = dict(gl_movement["summary"])
        summary["valuation_source"] = "gl"
        summary["gl_account_no"] = gl_movement["account_no"]
        summary["gl_account_name"] = gl_movement["account_name"]

        stock_in_bd, stock_out_bd = service._compute_gl_period_breakdown(
            start_date, end_date, branch
        )
        summary["stock_in_breakdown"] = stock_in_bd
        summary["stock_out_breakdown"] = stock_out_bd

        movement_by_entry_type = []
        try:
            movement_by_entry_type = service._compute_movement_by_entry_type(
                start_date, end_date, branch
            )
        except Exception as exc:
            self.stdout.write(
                self.style.WARNING(
                    f"  VE entry-type breakdown skipped ({exc}). "
                    "Using qty-rule totals only."
                )
            )
            movement_by_entry_type = self._movement_by_entry_type_python(
                start_date, end_date, branch
            )

        ve_totals = service._compute_value_entry_totals(
            start_date, end_date, branch
        )
        opening_gl = summary.get("opening_value", 0)
        closing_gl = summary.get("closing_value", 0)
        summary["value_entry_reconciliation"] = {
            "available": True,
            "opening_balance": ve_totals["opening_value"],
            "closing_balance": ve_totals["closing_value"],
            "inbound_balance": ve_totals["inbound_value"],
            "outbound_balance": ve_totals["outbound_value"],
            "opening_variance": float(
                round(opening_gl - ve_totals["opening_value"], 2)
            ),
            "closing_variance": float(
                round(closing_gl - ve_totals["closing_value"], 2)
            ),
            "period_inbound_variance": float(
                round(summary.get("inbound_value", 0) - ve_totals["inbound_value"], 2)
            ),
            "period_outbound_variance": float(
                round(summary.get("outbound_value", 0) - ve_totals["outbound_value"], 2)
            ),
            "ve_stock_in_breakdown": InventoryValueMovementService._breakdown_lines_from_entry_types(
                movement_by_entry_type, direction="in"
            ),
            "ve_stock_out_breakdown": InventoryValueMovementService._breakdown_lines_from_entry_types(
                movement_by_entry_type, direction="out"
            ),
        }
        ve = summary["value_entry_reconciliation"]

        gl_open = summary.get("opening_value", 0)
        gl_in = summary.get("inbound_value", 0)
        gl_out = summary.get("outbound_value", 0)
        gl_close = summary.get("closing_value", 0)
        gl_net = summary.get("net_change", 0)

        ve_open = ve.get("opening_balance", 0)
        ve_in = ve.get("inbound_balance", 0)
        ve_out = ve.get("outbound_balance", 0)
        ve_close = ve.get("closing_balance", 0)
        ve_net = float(round(ve_in - ve_out, 2))

        in_var = ve.get("period_inbound_variance", gl_in - ve_in)
        out_var = ve.get("period_outbound_variance", gl_out - ve_out)
        close_var = ve.get("closing_variance", gl_close - ve_close)
        open_var = ve.get("opening_variance", gl_open - ve_open)

        self.stdout.write(f"  G/L opening:        {_money(gl_open)}")
        self.stdout.write(f"  ValueEntry opening: {_money(ve_open)}  variance: {_money(open_var)}")
        self.stdout.write(f"  G/L period stock in:  {_money(gl_in)}")
        self.stdout.write(f"  VE period stock in:   {_money(ve_in)}  variance: {_money(in_var)}")
        self.stdout.write(f"  G/L period stock out: {_money(gl_out)}")
        self.stdout.write(f"  VE period stock out:  {_money(ve_out)}  variance: {_money(out_var)}")
        self.stdout.write(f"  G/L net change:       {_money(gl_net)}")
        self.stdout.write(f"  VE net change:        {_money(ve_net)}")
        self.stdout.write(f"  G/L closing:          {_money(gl_close)}")
        self.stdout.write(f"  VE closing:           {_money(ve_close)}  variance: {_money(close_var)}")

        sym_sum = float(round(in_var + out_var, 2))
        net_var = float(round(gl_net - ve_net, 2))
        double_neg = float(round(abs(in_var) * 2, 2)) if in_var and out_var else 0

        self.stdout.write("")
        self.stdout.write("  Checks:")
        self.stdout.write(
            f"    inbound_variance + outbound_variance = {_money(sym_sum)} "
            f"({'symmetric' if abs(sym_sum) < 0.02 else 'NOT symmetric'})"
        )
        self.stdout.write(
            f"    closing_variance vs (GL net - VE net) = {_money(close_var)} vs {_money(net_var)} "
            f"({'match' if abs(close_var - net_var) < 0.02 else 'mismatch'})"
        )
        if abs(in_var) > 0.01 and abs(in_var + out_var) < 0.02:
            self.stdout.write(
                self.style.WARNING(
                    f"    Symmetric ±{_money(abs(in_var))} on in/out → typical of one amount "
                    f"classified on opposite sides (e.g. negative adjustment)."
                )
            )
            if abs(close_var - 2 * in_var) < 0.02 or abs(close_var + 2 * in_var) < 0.02:
                self.stdout.write(
                    self.style.WARNING(
                        f"    closing_variance ≈ 2 × period swing ({_money(double_neg)}) "
                        f"when opening matches."
                    )
                )

        self.stdout.write("\n  G/L period breakdown (metric cards):")
        for line in summary.get("stock_in_breakdown") or []:
            self.stdout.write(
                f"    Stock in  {line['label']}: {_money(line['amount'])} "
                f"({line['transaction_count']} lines)"
            )
        for line in summary.get("stock_out_breakdown") or []:
            self.stdout.write(
                f"    Stock out {line['label']}: {_money(line['amount'])} "
                f"({line['transaction_count']} lines)"
            )

        self.stdout.write("\n  ValueEntry breakdown (entry-type category, not qty rule):")
        for line in ve.get("ve_stock_in_breakdown") or []:
            self.stdout.write(
                f"    Stock in  {line['label']}: {_money(line['amount'])} "
                f"({line['transaction_count']} rows)"
            )
        for line in ve.get("ve_stock_out_breakdown") or []:
            self.stdout.write(
                f"    Stock out {line['label']}: {_money(line['amount'])} "
                f"({line['transaction_count']} rows)"
            )

        ve_in_qty, ve_out_qty = self._ve_period_totals_qty_rule(start_date, end_date, branch)
        self.stdout.write("\n  ValueEntry period totals (qty>0 / qty<0 rule — used in comparison column):")
        self.stdout.write(f"    Stock in (qty>0):  {_money(ve_in_qty)}")
        self.stdout.write(f"    Stock out (qty<0): {_money(ve_out_qty)}")
        if abs(ve_in_qty - ve_in) > 0.01 or abs(ve_out_qty - ve_out) > 0.01:
            self.stdout.write(
                self.style.WARNING(
                    "    VE column totals match qty rule; sub-rows use entry-type category "
                    "(they may not sum to column totals)."
                )
            )

        self._last_in_var = in_var
        self._last_out_var = out_var
        self._last_close_var = close_var
        self._last_open_var = open_var
        self._last_branch_gl_untagged = gl_movement.get("branch_gl_untagged", False)

    @staticmethod
    def _parse_ve_cost(ve) -> float:
        return InventoryValueMovementService._parse_amount_field(ve.cost_amount)

    def _compute_value_entry_totals_python(self, start_date, end_date, branch):
        """Mirror _compute_value_entry_totals without SQL cast on cost_amount."""
        period_in, period_out = self._ve_period_totals_qty_rule(
            start_date, end_date, branch
        )
        opening_qs = ValueEntry.objects.filter(
            posting_date__lt=start_date,
            reversed=False,
        )
        if branch:
            opening_qs = opening_qs.filter(global_dimension_1=branch)
        opening_in = Decimal("0")
        opening_out = Decimal("0")
        for ve in opening_qs.only("cost_amount", "item_ledger_entry_quantity").iterator():
            cost = Decimal(str(self._parse_ve_cost(ve)))
            qty = ve.item_ledger_entry_quantity or 0
            if qty > 0:
                opening_in += cost
            elif qty < 0:
                opening_out += abs(cost)
        opening_value = float(round(opening_in - opening_out, 2))
        net_change = float(round(period_in - period_out, 2))
        closing_value = float(round(opening_value + net_change, 2))
        return {
            "opening_value": opening_value,
            "inbound_value": period_in,
            "outbound_value": period_out,
            "net_change": net_change,
            "closing_value": closing_value,
        }

    def _ve_period_totals_qty_rule(self, start_date, end_date, branch):
        qs = ValueEntry.objects.filter(
            posting_date__range=[start_date, end_date],
            reversed=False,
        )
        if branch:
            qs = qs.filter(global_dimension_1=branch)
        inbound = Decimal("0")
        outbound = Decimal("0")
        for ve in qs.only("cost_amount", "item_ledger_entry_quantity").iterator():
            cost = Decimal(str(self._parse_ve_cost(ve)))
            qty = ve.item_ledger_entry_quantity or 0
            if qty > 0:
                inbound += cost
            elif qty < 0:
                outbound += abs(cost)
        return float(inbound), float(outbound)

    def _movement_by_entry_type_python(self, start_date, end_date, branch):
        """Fallback when SQL Cast(cost_amount) fails on empty strings."""
        from collections import defaultdict

        qs = ValueEntry.objects.filter(
            posting_date__range=[start_date, end_date],
            reversed=False,
        )
        if branch:
            qs = qs.filter(global_dimension_1=branch)

        buckets = defaultdict(lambda: {"cost": Decimal("0"), "count": 0})
        for ve in qs.only("entry_type", "cost_amount").iterator():
            et = ve.entry_type or ""
            buckets[et]["cost"] += abs(Decimal(str(self._parse_ve_cost(ve))))
            buckets[et]["count"] += 1

        rows = []
        for entry_type, data in buckets.items():
            category = InventoryValueMovementService._entry_type_category(entry_type)
            total = float(round(data["cost"], 2))
            if total == 0:
                continue
            stock_in = total if category == "Stock In" else 0.0
            stock_out = total if category == "Stock Out" else 0.0
            rows.append(
                {
                    "entry_type": entry_type,
                    "entry_type_label": InventoryValueMovementService._entry_type_label(
                        entry_type
                    ),
                    "category": category,
                    "transaction_count": data["count"],
                    "stock_in_value": stock_in,
                    "stock_out_value": stock_out,
                }
            )
        return rows

    def _section_negative_adjustment_audit(self, start_date, end_date, branch):
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("2) Negative adjustment sign audit"))

        neg_types = [
            EntryType.NegativeAdjustment.name,
            EntryType.NegativeAdjustment.value,
            "NegativeAdjustment",
        ]
        qs = ValueEntry.objects.filter(
            posting_date__range=[start_date, end_date],
            reversed=False,
            entry_type__in=neg_types,
        )
        if branch:
            qs = qs.filter(global_dimension_1=branch)

        n = qs.count()
        inbound_mis = Decimal("0")
        outbound_ok = Decimal("0")
        qty_pos_count = qty_neg_count = qty_zero_count = 0
        for ve in qs.only("cost_amount", "item_ledger_entry_quantity").iterator():
            cost = Decimal(str(self._parse_ve_cost(ve)))
            qty = ve.item_ledger_entry_quantity or 0
            if qty > 0:
                qty_pos_count += 1
                inbound_mis += cost
            elif qty < 0:
                qty_neg_count += 1
                outbound_ok += abs(cost)
            else:
                qty_zero_count += 1

        inbound_mis = float(inbound_mis)
        outbound_ok = float(outbound_ok)

        self.stdout.write(f"  ValueEntry negative adjustment rows: {n}")
        self.stdout.write(f"    qty > 0 (counted as period STOCK IN by report):  {qty_pos_count}  sum cost: {_money(inbound_mis)}")
        self.stdout.write(f"    qty < 0 (counted as period STOCK OUT by report): {qty_neg_count}  sum cost: {_money(outbound_ok)}")
        self.stdout.write(f"    qty = 0: {qty_zero_count}")

        account, gl_qs, _ = InventoryValueMovementService._resolve_gl_queryset(branch)
        gl_neg_out = 0.0
        gl_neg_n = 0
        if account and gl_qs is not None:
            gl_neg = gl_qs.filter(
                posting_date__range=[start_date, end_date],
                description__icontains="Negative Adjustment",
                amount__lt=0,
            )
            gl_agg = gl_neg.aggregate(n=Count("id"), t=Sum("amount"))
            gl_neg_n = gl_agg["n"] or 0
            gl_neg_out = abs(float(gl_agg["t"] or 0))

        self.stdout.write(f"  G/L 2110 negative adjustment credits: {gl_neg_n}  sum: {_money(gl_neg_out)}")

        in_var = getattr(self, "_last_in_var", 0)
        if abs(inbound_mis - abs(in_var)) < 1.0 and inbound_mis > 0:
            self.stdout.write(
                self.style.ERROR(
                    f"  CONFIRMED: qty>0 negative adjustments ({_money(inbound_mis)}) "
                    f"≈ period inbound variance ({_money(in_var)}). "
                    f"These rows inflate VE stock-in and reduce VE stock-out vs G/L."
                )
            )
        elif inbound_mis > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"  Partial: qty>0 negative adjustment cost {_money(inbound_mis)} "
                    f"(report inbound variance {_money(in_var)})."
                )
            )
        else:
            self.stdout.write(
                "  All negative adjustments have qty<=0 on ValueEntry; "
                "look for other entry types or branch/period mismatch."
            )

        self._neg_inbound_mis = inbound_mis
        self._gl_neg_out = gl_neg_out

    def _section_document_tie_out(self, start_date, end_date, branch, sample_docs):
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("3) Document tie-out samples"))

        neg_types = [
            EntryType.NegativeAdjustment.name,
            EntryType.NegativeAdjustment.value,
            "NegativeAdjustment",
        ]
        qs = ValueEntry.objects.filter(
            posting_date__range=[start_date, end_date],
            reversed=False,
            entry_type__in=neg_types,
            item_ledger_entry_quantity__gt=0,
        )
        if branch:
            qs = qs.filter(global_dimension_1=branch)

        doc_nos = (
            qs.values_list("document_no", flat=True)
            .distinct()
            .order_by("document_no")[:sample_docs]
        )

        if not doc_nos:
            qs_any = ValueEntry.objects.filter(
                posting_date__range=[start_date, end_date],
                reversed=False,
                entry_type__in=neg_types,
            )
            if branch:
                qs_any = qs_any.filter(global_dimension_1=branch)
            doc_nos = list(
                qs_any.values_list("document_no", flat=True)
                .distinct()
                .order_by("-posting_date")[:sample_docs]
            )

        account = InventoryValueMovementService._resolve_resale_items_gl_account()

        for doc_no in doc_nos:
            if not doc_no:
                continue
            self.stdout.write(f"\n  --- document_no: {doc_no} ---")
            for ve in ValueEntry.objects.filter(document_no=doc_no, reversed=False).order_by(
                "id"
            )[:5]:
                self.stdout.write(
                    f"    VE id={ve.id} type={ve.entry_type!r} qty={ve.item_ledger_entry_quantity} "
                    f"cost={ve.cost_amount!r} date={ve.posting_date}"
                )
            for ile in ItemLedgerEntries.objects.filter(document_no=doc_no).order_by(
                "id"
            )[:5]:
                self.stdout.write(
                    f"    ILE id={ile.id} type={ile.entry_type!r} qty={ile.quantity} "
                    f"remaining={ile.remaining_quantity}"
                )
            if account:
                for gl in GeneralLedgerEntry.objects.filter(
                    gl_account=account, document_no=doc_no
                ).order_by("id")[:6]:
                    self.stdout.write(
                        f"    GL id={gl.id} amt={gl.amount} type={gl.general_posting_type!r} "
                        f"desc={((gl.description or '')[:60])!r}"
                    )

    def _section_purchase_tie_out(self, start_date, end_date, branch):
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("4) Purchase tie-out"))

        account, gl_qs, _ = InventoryValueMovementService._resolve_gl_queryset(branch)
        gl_purchase = 0.0
        gl_purchase_n = 0
        if account and gl_qs is not None:
            gl_p = gl_qs.filter(
                posting_date__range=[start_date, end_date],
                general_posting_type="Purchase",
                amount__gt=0,
            )
            a = gl_p.aggregate(n=Count("id"), t=Sum("amount"))
            gl_purchase_n = a["n"] or 0
            gl_purchase = float(a["t"] or 0)

        purchase_types = [
            EntryType.Purchase.name,
            EntryType.Purchase.value,
            "Purchase",
        ]
        ve_qs = ValueEntry.objects.filter(
            posting_date__range=[start_date, end_date],
            reversed=False,
            entry_type__in=purchase_types,
        )
        if branch:
            ve_qs = ve_qs.filter(global_dimension_1=branch)

        ve_in = Decimal("0")
        ve_cat = Decimal("0")
        ve_n = 0
        for ve in ve_qs.only("cost_amount", "item_ledger_entry_quantity").iterator():
            ve_n += 1
            cost = Decimal(str(self._parse_ve_cost(ve)))
            ve_cat += abs(cost)
            if (ve.item_ledger_entry_quantity or 0) > 0:
                ve_in += cost
        ve_in = float(ve_in)
        ve_cat = float(ve_cat)

        self.stdout.write(f"  G/L 2110 Purchase (positive): {_money(gl_purchase)} ({gl_purchase_n} lines)")
        self.stdout.write(
            f"  VE Purchase rows: {ve_n}  sum cost (qty>0 rule): {_money(ve_in)}  "
            f"sum all cost: {_money(abs(ve_cat))}"
        )
        self.stdout.write(
            f"  Gap (G/L purchase - VE purchase qty>0): {_money(gl_purchase - ve_in)}"
        )

        if account and gl_qs is not None:
            gl_docs = set(
                gl_qs.filter(
                    posting_date__range=[start_date, end_date],
                    general_posting_type="Purchase",
                    amount__gt=0,
                ).values_list("document_no", flat=True)
            )
            ve_docs = set(ve_qs.values_list("document_no", flat=True))
            only_gl = sorted(d for d in gl_docs if d and d not in ve_docs)[:10]
            only_ve = sorted(d for d in ve_docs if d and d not in gl_docs)[:10]
            if only_gl:
                self.stdout.write(f"  document_no on G/L only (first 10): {only_gl}")
            if only_ve:
                self.stdout.write(f"  document_no on VE only (first 10): {only_ve}")

    def _section_opening_variance_audit(self, start_date, branch):
        """Trace opening-only G/L vs ValueEntry gap (e.g. UGX 2,200 carried into closing)."""
        from collections import defaultdict

        open_var = getattr(self, "_last_open_var", 0)
        if abs(open_var) < 0.01:
            return

        service = InventoryValueMovementService()
        opening_as_of = start_date - timedelta(days=1)
        account, gl_qs, branch_gl_untagged = service._resolve_gl_queryset(branch)
        if not account or gl_qs is None:
            return

        gl_open = float(service._gl_balance_as_of(gl_qs, opening_as_of))
        opening_ve_qs = ValueEntry.objects.filter(
            posting_date__lt=start_date,
            reversed=False,
        )
        if branch:
            opening_ve_qs = opening_ve_qs.filter(global_dimension_1=branch)
        ve_in, ve_out = service._sum_value_entries_by_category(opening_ve_qs)
        ve_open = float(ve_in - ve_out)

        self.stdout.write("")
        self.stdout.write(
            self.style.MIGRATE_HEADING("6) Opening variance audit (before period start)")
        )
        self.stdout.write(f"  Opening as-of: {opening_as_of} (day before {start_date})")
        self.stdout.write(f"  G/L opening:        {_money(gl_open)}")
        self.stdout.write(f"  ValueEntry opening: {_money(ve_open)}")
        self.stdout.write(
            self.style.WARNING(f"  Variance (G/L - VE): {_money(open_var)}")
        )

        in_var = getattr(self, "_last_in_var", 0)
        out_var = getattr(self, "_last_out_var", 0)
        if abs(in_var) < 0.01 and abs(out_var) < 0.01:
            self.stdout.write(
                self.style.WARNING(
                    "  Period stock in/out match — this variance existed BEFORE the "
                    "selected period and is carried into closing unchanged."
                )
            )

        untagged = getattr(self, "_last_branch_gl_untagged", branch_gl_untagged)
        if untagged:
            self.stdout.write(
                self.style.WARNING(
                    "  branch_gl_untagged: G/L 2110 may include company-wide lines while "
                    "ValueEntry is branch-filtered — common opening-only gap."
                )
            )

        gl_before = gl_qs.filter(posting_date__lte=opening_as_of)

        ve_by_type = defaultdict(lambda: {"in": 0.0, "out": 0.0, "count": 0})
        for ve in opening_ve_qs.only("entry_type", "document_type", "cost_amount"):
            amount = float(service._value_entry_cost_abs(ve.cost_amount))
            effective = service._effective_entry_type(ve.entry_type, ve.document_type)
            category = service._entry_type_category(effective)
            bucket = ve_by_type[effective or "Unknown"]
            bucket["count"] += 1
            if category == "Stock In":
                bucket["in"] += amount
            else:
                bucket["out"] += amount

        self.stdout.write("\n  ValueEntry opening by entry type (category rules):")
        for entry_type, data in sorted(ve_by_type.items()):
            net = data["in"] - data["out"]
            self.stdout.write(
                f"    {entry_type}: in {_money(data['in'])} out {_money(data['out'])} "
                f"net {_money(net)} ({data['count']} rows)"
            )

        gl_doc_set = {
            d
            for d in gl_before.exclude(document_no__isnull=True)
            .exclude(document_no="")
            .values_list("document_no", flat=True)
            if d
        }
        ve_doc_set = {
            d
            for d in opening_ve_qs.exclude(document_no__isnull=True)
            .exclude(document_no="")
            .values_list("document_no", flat=True)
            if d
        }
        only_gl = sorted(gl_doc_set - ve_doc_set)
        only_ve = sorted(ve_doc_set - gl_doc_set)

        gl_only_net = Decimal("0")
        for doc_no in only_gl:
            gl_only_net += service._to_decimal(
                gl_before.filter(document_no=doc_no).aggregate(t=Sum("amount"))["t"]
            )

        ve_only_net = Decimal("0")
        for doc_no in only_ve:
            doc_qs = opening_ve_qs.filter(document_no=doc_no)
            doc_in, doc_out = service._sum_value_entries_by_category(doc_qs)
            ve_only_net += doc_in - doc_out

        self.stdout.write(
            f"\n  G/L-only document_no before {start_date}: {len(only_gl)} docs, "
            f"net G/L sum {_money(gl_only_net)}"
        )
        self.stdout.write(
            f"  ValueEntry-only document_no before {start_date}: {len(only_ve)} docs, "
            f"net VE sum {_money(ve_only_net)}"
        )

        top_gl_only = []
        for doc_no in only_gl:
            net = float(
                gl_before.filter(document_no=doc_no).aggregate(t=Sum("amount"))["t"] or 0
            )
            if abs(net) >= 0.01:
                top_gl_only.append((doc_no, net))
        top_gl_only.sort(key=lambda row: abs(row[1]), reverse=True)
        if top_gl_only:
            self.stdout.write("  Top G/L-only docs (no ValueEntry before period):")
            for doc_no, net in top_gl_only[:12]:
                self.stdout.write(f"    {doc_no}: G/L net {_money(net)}")

        doc_gaps = []
        for doc_no in gl_doc_set & ve_doc_set:
            gl_net = float(
                gl_before.filter(document_no=doc_no).aggregate(t=Sum("amount"))["t"] or 0
            )
            doc_qs = opening_ve_qs.filter(document_no=doc_no)
            doc_in, doc_out = service._sum_value_entries_by_category(doc_qs)
            ve_net = float(doc_in - doc_out)
            gap = round(gl_net - ve_net, 2)
            if abs(gap) >= 0.01:
                doc_gaps.append((doc_no, gap, gl_net, ve_net))
        doc_gaps.sort(key=lambda row: abs(row[1]), reverse=True)
        if doc_gaps:
            self.stdout.write(
                "\n  Matched document_no with tie-out gap (G/L net - VE net):"
            )
            gap_sum = 0.0
            for doc_no, gap, gl_net, ve_net in doc_gaps[:15]:
                self.stdout.write(
                    f"    {doc_no}: gap {_money(gap)}  "
                    f"(G/L {_money(gl_net)}, VE {_money(ve_net)})"
                )
                gap_sum += gap
            self.stdout.write(
                f"    (top {min(15, len(doc_gaps))} gaps sum {_money(gap_sum)})"
            )

        untagged_sum = 0.0
        if branch is not None:
            untagged_gl = gl_before.filter(global_dimension_1__isnull=True)
            untagged_sum = float(
                untagged_gl.aggregate(t=Sum("amount"))["t"] or 0
            )
            self.stdout.write(
                f"\n  G/L 2110 before period with NULL global_dimension_1: "
                f"{untagged_gl.count()} lines, sum {_money(untagged_sum)}"
            )
            ve_null = ValueEntry.objects.filter(
                posting_date__lt=start_date,
                reversed=False,
                global_dimension_1__isnull=True,
            )
            null_in, null_out = service._sum_value_entries_by_category(ve_null)
            self.stdout.write(
                f"  ValueEntry before period with NULL branch: net "
                f"{_money(float(null_in - null_out))} ({ve_null.count()} rows)"
            )

        for amount in (open_var, -open_var, 2200, -2200):
            hits = gl_before.filter(amount=amount)
            if hits.exists():
                self.stdout.write(
                    f"\n  G/L lines with amount exactly {_money(amount)} before period:"
                )
                for gl in hits[:8]:
                    desc = (gl.description or "")[:70]
                    self.stdout.write(
                        f"    id={gl.id} doc={gl.document_no!r} date={gl.posting_date} "
                        f"branch={gl.global_dimension_1_id} desc={desc!r}"
                    )

        if abs(float(gl_only_net) - open_var) < 1.0:
            self.stdout.write(
                self.style.ERROR(
                    f"\n  LIKELY CAUSE: G/L-only postings (no ValueEntry) ≈ variance "
                    f"({_money(gl_only_net)})."
                )
            )
        elif abs(float(untagged_sum) - open_var) < 1.0 and branch is not None:
            self.stdout.write(
                self.style.ERROR(
                    f"\n  LIKELY CAUSE: untagged G/L 2110 lines ≈ variance "
                    f"({_money(untagged_sum)}). Run branch dimension backfill."
                )
            )

    def _section_recommendation(self):
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("7) Recommended fix scope"))
        inbound_mis = getattr(self, "_neg_inbound_mis", 0)
        in_var = getattr(self, "_last_in_var", 0)
        open_var = getattr(self, "_last_open_var", 0)

        if abs(open_var) > 0.01 and abs(in_var) < 0.01 and abs(getattr(self, "_last_out_var", 0)) < 0.01:
            self.stdout.write(
                self.style.WARNING(
                    f"PRIMARY: Opening-only variance {_money(open_var)} — fix historical "
                    f"data before period start (section 6): missing ValueEntry for G/L 2110, "
                    f"branch tagging, or document tie-out gaps."
                )
            )
            self.stdout.write(
                "  - Compare G/L-only document_no list with purchase/adjustment posting"
            )
            self.stdout.write(
                "  - Backfill global_dimension_1 on old G/L / ValueEntry if branch filter used"
            )
        elif inbound_mis > 0 and abs(inbound_mis - abs(in_var)) < 1.0:
            self.stdout.write(
                self.style.WARNING(
                    "PRIMARY: ValueEntry negative adjustments with positive quantity "
                    "(or positive cost with qty>0) — data/posting fix recommended."
                )
            )
            self.stdout.write("  - Repost or correct affected item journals / value entries")
            self.stdout.write("  - Harden items/admin.py and import paths (already negate in _create_value_entries)")
            self.stdout.write(
                "  SECONDARY: Align report VE comparison totals to entry-type category "
                "(so sub-rows sum to column totals) — report-only, does not fix books."
            )
        else:
            self.stdout.write(
                "Review branch filter, period dates, and entry types in section 2–4. "
                "If variances persist, enable verbose samples and compare opening formulas."
            )
        self.stdout.write("")
