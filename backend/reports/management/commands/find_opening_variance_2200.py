"""Quick opening G/L vs VE gap finder — primewise CENTRAL Jun 2026."""

from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import connection
from django.db.models import Sum

from django_tenants.utils import schema_context

from dimension.models import DimensionValue
from financials.models import GeneralLedgerEntry
from items.models import ValueEntry
from reports.services.inventory_value_movement_service import InventoryValueMovementService


class Command(BaseCommand):
    help = "Find source of opening G/L vs VE variance for a tenant/branch."

    def add_arguments(self, parser):
        parser.add_argument("--schema", default="")
        parser.add_argument("--branch-code", default="CENTRAL")
        parser.add_argument("--start", default="2026-06-01")

    def handle(self, *args, **options):
        start = date.fromisoformat(options["start"])
        opening_asof = start - timedelta(days=1)
        schema = (options.get("schema") or "").strip()
        if not schema:
            tenant = getattr(connection, "tenant", None)
            schema = getattr(tenant, "schema_name", None) or ""
        if not schema or schema == "public":
            self.stderr.write("Pass --schema or run via tenant_command <schema> ...")
            return

        def run():
            branch = DimensionValue.objects.filter(
                code__iexact=options["branch_code"]
            ).first()
            if not branch:
                self.stderr.write("Branch not found")
                return

            svc = InventoryValueMovementService()
            account, gl_qs, _ = svc._resolve_gl_queryset(branch)
            gl_before = gl_qs.filter(posting_date__lte=opening_asof)
            ve_before = ValueEntry.objects.filter(
                posting_date__lt=start, reversed=False, global_dimension_1=branch
            )

            gl_open = float(svc._gl_balance_as_of(gl_qs, opening_asof))
            vi, vo = svc._sum_value_entries_by_category(ve_before)
            ve_open = float(vi - vo)
            var = round(gl_open - ve_open, 2)

            self.stdout.write(f"Tenant: {schema}  Branch: {branch.code}")
            self.stdout.write(f"Opening as-of: {opening_asof}")
            self.stdout.write(f"G/L opening: {gl_open:,.2f}")
            self.stdout.write(f"VE opening:  {ve_open:,.2f}")
            self.stdout.write(f"Variance:    {var:,.2f}")

            # G/L lines amount exactly +/- variance
            for amt in (var, -var, 2200, -2200):
                rows = gl_before.filter(amount=amt)[:20]
                if rows.exists():
                    self.stdout.write(f"\nG/L lines with amount {amt}:")
                    for gl in rows:
                        self.stdout.write(
                            f"  id={gl.id} date={gl.posting_date} doc={gl.document_no!r} "
                            f"branch_id={gl.global_dimension_1_id} "
                            f"desc={(gl.description or '')[:80]!r}"
                        )

            # Untagged G/L on 2110 before period
            untagged = gl_before.filter(global_dimension_1__isnull=True)
            ut_sum = float(untagged.aggregate(t=Sum("amount"))["t"] or 0)
            self.stdout.write(
                f"\nG/L 2110 before period, NULL branch: {untagged.count()} lines, "
                f"sum {ut_sum:,.2f}"
            )

            # Aggregate G/L by document_no (fast)
            gl_by_doc = {
                row["document_no"]: float(row["total"] or 0)
                for row in gl_before.exclude(document_no="")
                .exclude(document_no__isnull=True)
                .values("document_no")
                .annotate(total=Sum("amount"))
            }
            ve_doc_totals = {}
            for ve in ve_before.only(
                "document_no", "entry_type", "document_type", "cost_amount"
            ).iterator(chunk_size=5000):
                doc = ve.document_no or ""
                if not doc:
                    continue
                cost = float(svc._value_entry_cost_abs(ve.cost_amount))
                eff = svc._effective_entry_type(ve.entry_type, ve.document_type)
                cat = svc._entry_type_category(eff)
                sign = 1 if cat == "Stock In" else -1
                ve_doc_totals[doc] = ve_doc_totals.get(doc, 0.0) + sign * cost

            gl_only = []
            ve_only = []
            matched_gaps = []
            for doc, gl_net in gl_by_doc.items():
                ve_net = ve_doc_totals.get(doc)
                if ve_net is None:
                    gl_only.append((doc, gl_net))
                elif abs(round(gl_net - ve_net, 2)) >= 0.01:
                    matched_gaps.append((doc, round(gl_net - ve_net, 2), gl_net, ve_net))
            for doc, ve_net in ve_doc_totals.items():
                if doc not in gl_by_doc:
                    ve_only.append((doc, ve_net))

            gl_only.sort(key=lambda x: abs(x[1]), reverse=True)
            matched_gaps.sort(key=lambda x: abs(x[1]), reverse=True)
            ve_only.sort(key=lambda x: abs(x[1]), reverse=True)

            gl_only_sum = sum(n for _, n in gl_only)
            self.stdout.write(
                f"\nG/L-only document_no (no VE before {start}): {len(gl_only)} docs, "
                f"net sum {gl_only_sum:,.2f}"
            )
            for doc, net in gl_only[:12]:
                self.stdout.write(f"  {doc}: {net:,.2f}")

            self.stdout.write(f"\nVE-only document_no: {len(ve_only)} docs")
            for doc, net in ve_only[:8]:
                self.stdout.write(f"  {doc}: {net:,.2f}")

            self.stdout.write(f"\nMatched docs with gap (top 12):")
            gap_sum = 0.0
            for doc, gap, gl_n, ve_n in matched_gaps[:12]:
                self.stdout.write(
                    f"  {doc}: gap {gap:,.2f}  (G/L {gl_n:,.2f}, VE {ve_n:,.2f})"
                )
                gap_sum += gap
            if matched_gaps:
                self.stdout.write(f"  (top 12 gaps sum {gap_sum:,.2f})")

            if abs(gl_only_sum - var) < 1:
                self.stdout.write(
                    self.style.ERROR(
                        f"\nLIKELY: G/L-only postings net {gl_only_sum:,.2f} ~= variance"
                    )
                )
            elif abs(ut_sum - var) < 1:
                self.stdout.write(
                    self.style.ERROR(
                        f"\nLIKELY: Untagged G/L sum {ut_sum:,.2f} ~= variance"
                    )
                )
            elif matched_gaps and abs(matched_gaps[0][1] - var) < 1:
                d, g, _, _ = matched_gaps[0]
                self.stdout.write(
                    self.style.ERROR(f"\nLIKELY: Document {d} gap {g:,.2f} ~= variance")
                )

        if schema_context and schema:
            with schema_context(schema):
                run()
        else:
            run()
