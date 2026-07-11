"""Inventory Transaction Detail report — BC-style running qty balance with cost columns."""

from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db.models import DecimalField, Q, Sum
from django.db.models.functions import Cast

from items.models import Item, ItemLedgerEntries, ValueEntry
from items.value_entry_posting import parse_cost_amount

from .base_report_service import BaseReportService
from .inventory_value_movement_service import InventoryValueMovementService

_COST_CAST = Cast("cost_amount", output_field=DecimalField(max_digits=20, decimal_places=4))


class InventoryTransactionDetailService(BaseReportService):
    """Per-item ledger with opening balance, period movements, and running qty/cost."""

    def _branch_filter(self, branch=None):
        """Match Items list / ItemSerializer: branch dimension only (not location)."""
        filters = {}
        if branch is not None and branch != "all":
            filters["global_dimension_1"] = branch
        return filters

    def _branch_q(self, branch=None):
        q = Q()
        if branch is not None and branch != "all":
            q &= Q(global_dimension_1=branch)
        return q

    @staticmethod
    def _signed_cost_for_qty(quantity: int, cost: Decimal) -> Decimal:
        """
        Inventory value follows movement direction: stock in adds cost, stock out subtracts.
        Value Entry rows may store mixed signs in legacy data — align to ILE quantity sign.
        """
        cost_abs = abs(cost)
        if quantity > 0:
            return cost_abs
        if quantity < 0:
            return -cost_abs
        return Decimal("0")

    def _cost_map_for_iles(self, ile_ids):
        if not ile_ids:
            return {}
        rows = (
            ValueEntry.objects.filter(
                item_ledger_entry_no_id__in=ile_ids,
                reversed=False,
            )
            .values("item_ledger_entry_no_id")
            .annotate(cost=Sum(_COST_CAST))
        )
        return {
            row["item_ledger_entry_no_id"]: parse_cost_amount(row["cost"])
            for row in rows
        }

    def _sum_signed_cost_for_iles(self, ile_qs, cost_map: dict) -> Decimal:
        total = Decimal("0")
        for row in ile_qs.values("id", "quantity"):
            raw = cost_map.get(row["id"], Decimal("0"))
            total += self._signed_cost_for_qty(row["quantity"] or 0, raw)
        return total

    def _item_uom_label(self, item):
        uom = item.unit_of_measure
        if uom is None:
            return "PCS"
        return getattr(uom, "code", None) or str(uom)

    def get_report(
        self,
        start_date: date,
        end_date: date,
        branch=None,
        item_no: str = None,
        entry_type: str = None,
        only_with_activity: bool = False,
    ) -> dict:
        self.validate_filters({"start_date": start_date, "end_date": end_date})

        base_q = (
            Q(posting_date__lte=end_date)
            & Q(reversed=False)
            & self._branch_q(branch)
        )
        if item_no:
            base_q &= Q(item__no=item_no)

        # Item.pk is `no` (CharField), not numeric id — item_id column stores item numbers.
        item_keys = (
            ItemLedgerEntries.objects.filter(base_q)
            .values_list("item_id", flat=True)
            .distinct()
        )
        items = Item.objects.filter(pk__in=item_keys).order_by("no").select_related(
            "unit_of_measure"
        )

        branch_filter = self._branch_filter(branch)
        result_items = []
        grand_total_increases = Decimal("0")
        grand_total_decreases = Decimal("0")
        grand_opening_cost = Decimal("0")
        grand_closing_cost = Decimal("0")

        for item in items:
            on_hand_qs = ItemLedgerEntries.objects.filter(
                item=item,
                reversed=False,
                **branch_filter,
            )
            # Current on-hand (Items list / inventory field) — remaining on open lots.
            current_qty = int(
                on_hand_qs.aggregate(s=Sum("remaining_quantity"))["s"] or 0
            )
            on_hand_iles = on_hand_qs.filter(remaining_quantity__gt=0)
            on_hand_ids = list(on_hand_iles.values_list("id", flat=True))
            current_cost_map = self._cost_map_for_iles(on_hand_ids)
            current_cost = self._sum_signed_cost_for_iles(on_hand_iles, current_cost_map)

            # All period movements (unfiltered) — used to back-calculate opening at period start.
            period_qs_all = ItemLedgerEntries.objects.filter(
                item=item,
                posting_date__range=[start_date, end_date],
                reversed=False,
                **branch_filter,
            )
            period_net_qty = int(
                period_qs_all.aggregate(s=Sum("quantity"))["s"] or 0
            )
            period_all_ids = list(period_qs_all.values_list("id", flat=True))
            period_all_cost_map = self._cost_map_for_iles(period_all_ids)
            period_net_cost = self._sum_signed_cost_for_iles(
                period_qs_all, period_all_cost_map
            )

            # Opening at period start = on-hand now minus net movement in the period.
            # Matches Items list and avoids stale remaining_quantity on old lots.
            opening_qty = current_qty - period_net_qty
            opening_cost = current_cost - period_net_cost
            if opening_qty < 0:
                opening_qty = 0
            if opening_cost < 0:
                opening_cost = Decimal("0")

            # Audit: raw ledger total before period (can be negative if history oversold).
            opening_iles = ItemLedgerEntries.objects.filter(
                item=item,
                posting_date__lt=start_date,
                reversed=False,
                **branch_filter,
            )
            ledger_opening_qty_int = int(
                opening_iles.aggregate(s=Sum("quantity"))["s"] or 0
            )
            opening_ile_ids = list(opening_iles.values_list("id", flat=True))
            ledger_opening_cost = self._sum_signed_cost_for_iles(
                opening_iles, self._cost_map_for_iles(opening_ile_ids)
            )
            has_ledger_deficit = ledger_opening_qty_int < 0
            ledger_opening_deficit = (
                abs(ledger_opening_qty_int) if has_ledger_deficit else 0
            )
            opening_differs_from_ledger = opening_qty != ledger_opening_qty_int

            period_qs = period_qs_all
            if entry_type:
                period_qs = period_qs.filter(entry_type=entry_type)

            period_entries = period_qs.order_by("posting_date", "id").select_related(
                "location"
            )
            ile_ids = list(period_entries.values_list("id", flat=True))
            cost_map = self._cost_map_for_iles(ile_ids)

            running_qty = opening_qty
            running_cost = opening_cost
            entries_out = []
            total_increases = Decimal("0")
            total_decreases = Decimal("0")
            total_cost_in = Decimal("0")
            total_cost_out = Decimal("0")

            for ile in period_entries:
                qty = ile.quantity
                raw_cost = cost_map.get(ile.id, Decimal("0"))
                cost = self._signed_cost_for_qty(qty, raw_cost)
                running_qty += qty
                running_cost += cost
                increases = qty if qty > 0 else 0
                decreases = abs(qty) if qty < 0 else 0
                total_increases += Decimal(increases)
                total_decreases += Decimal(decreases)
                if qty > 0:
                    total_cost_in += abs(raw_cost)
                elif qty < 0:
                    total_cost_out += abs(raw_cost)

                entries_out.append(
                    {
                        "id": ile.id,
                        "posting_date": (
                            ile.posting_date.isoformat() if ile.posting_date else None
                        ),
                        "entry_type": ile.entry_type,
                        "document_type": ile.document_type or "",
                        "document_no": ile.document_no,
                        "description": ile.description,
                        "location_code": (
                            ile.location.code if ile.location else None
                        ),
                        "increases": str(increases),
                        "decreases": str(decreases),
                        "qty_signed": str(qty),
                        "cost_amount": str(round(abs(raw_cost), 2)),
                        "running_qty": str(running_qty),
                        "running_cost": str(round(running_cost, 2)),
                        "remaining_quantity": str(ile.remaining_quantity),
                        "reversed": ile.reversed,
                        "reversed_by_document_no": ile.reversed_by_document_no
                        or None,
                    }
                )

            closing_qty = running_qty if entry_type else current_qty
            closing_cost = running_cost if entry_type else current_cost

            grand_total_increases += total_increases
            grand_total_decreases += total_decreases
            grand_opening_cost += opening_cost
            grand_closing_cost += closing_cost

            result_items.append(
                {
                    "item_no": item.no,
                    "item_name": item.item_name,
                    "unit_of_measure": self._item_uom_label(item),
                    "opening_qty": str(opening_qty),
                    "opening_cost": str(round(opening_cost, 2)),
                    "current_qty": str(current_qty),
                    "current_cost": str(round(current_cost, 2)),
                    "ledger_opening_qty": str(ledger_opening_qty_int),
                    "ledger_opening_cost": str(round(ledger_opening_cost, 2)),
                    "has_ledger_deficit": has_ledger_deficit,
                    "ledger_opening_deficit": str(ledger_opening_deficit),
                    "opening_differs_from_ledger": opening_differs_from_ledger,
                    "entries": entries_out,
                    "total_increases": str(total_increases),
                    "total_decreases": str(total_decreases),
                    "total_cost_in": str(round(total_cost_in, 2)),
                    "total_cost_out": str(round(total_cost_out, 2)),
                    "closing_qty": str(closing_qty),
                    "closing_cost": str(round(closing_cost, 2)),
                    "entry_count": len(entries_out),
                    "has_activity": len(entries_out) > 0,
                }
            )

        # Summary stock value = G/L 2110 (Resale Items), same as Sales dashboard STOCK VALUE card.
        gl_meta = InventoryValueMovementService._resolve_resale_items_gl_account()
        opening_as_of = start_date - timedelta(days=1)
        gl_current = Decimal(
            str(
                InventoryValueMovementService.get_sales_dashboard_stock_balance(branch)
            )
        )
        gl_opening = Decimal(
            str(
                InventoryValueMovementService.get_sales_dashboard_stock_balance(
                    branch, as_of=opening_as_of
                )
            )
        )
        gl_closing = Decimal(
            str(
                InventoryValueMovementService.get_sales_dashboard_stock_balance(
                    branch, as_of=end_date
                )
            )
        )

        # Opening = G/L 2110 through day before period; closing = through period end.
        # (Single-day ranges still have movement in the detail grid — do not pin both to current balance.)
        summary_opening = gl_opening
        summary_closing = gl_closing

        total_items_with_activity = sum(
            1 for i in result_items if i["has_activity"]
        )
        if only_with_activity:
            result_items = [i for i in result_items if i["has_activity"]]

        return {
            "start_date": str(start_date),
            "end_date": str(end_date),
            "generated_at": datetime.now().isoformat(),
            "items": result_items,
            "summary": {
                "total_items": len(result_items),
                "total_items_with_activity": total_items_with_activity,
                "grand_total_increases": str(grand_total_increases),
                "grand_total_decreases": str(grand_total_decreases),
                "grand_opening_cost": str(round(summary_opening, 2)),
                "grand_closing_cost": str(round(summary_closing, 2)),
                "grand_opening_cost_detail": str(round(grand_opening_cost, 2)),
                "grand_closing_cost_detail": str(round(grand_closing_cost, 2)),
                "stock_value_gl_opening": str(round(gl_opening, 2)),
                "stock_value_gl_closing": str(round(gl_closing, 2)),
                "stock_value_gl_current": str(round(gl_current, 2)),
                "valuation_source": "gl_2110",
                "gl_account_no": getattr(gl_meta, "no", "2110") if gl_meta else "2110",
                "gl_account_name": (
                    getattr(gl_meta, "name", "Resale Items")
                    if gl_meta
                    else "Resale Items"
                ),
            },
        }
