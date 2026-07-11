"""
Debug branch filter setup for Items.
Run: python manage.py tenant_command debug_branch_filter --schema=<schema>
"""

from django.core.management.base import BaseCommand

try:
    from django_tenants.utils import schema_context
except ImportError:
    schema_context = None


class Command(BaseCommand):
    help = "Debug branch filter setup for Items (multi-branch)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            type=str,
            help="Tenant schema name (use tenant_command for multi-tenant).",
        )

    def handle(self, *args, **options):
        schema_name = options.get("schema")

        def run():
            from financials.models import GeneralLedgerSetup
            from base.models import Objects
            from dimension.models import DefaultDimension, Dimension, DimensionValue

            self.stdout.write("\n=== Branch Filter Debug ===\n")

            # 1. GL Setup
            gl = GeneralLedgerSetup.objects.first()
            if not gl:
                self.stdout.write(self.style.ERROR("GeneralLedgerSetup not found."))
                return
            self.stdout.write(
                f"enable_multiple_branches: {getattr(gl, 'enable_multiple_branches', False)}"
            )
            self.stdout.write(f"global_dimension_1_id: {gl.global_dimension_1_id}")

            branch_dim_id = gl.global_dimension_1_id
            if not branch_dim_id:
                branch_dim = Dimension.objects.filter(code__iexact="BRANCH").first()
                if branch_dim:
                    branch_dim_id = branch_dim.id
                    self.stdout.write(
                        self.style.WARNING(
                            f"Using BRANCH dimension as fallback: id={branch_dim_id}"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(
                            "No branch dimension. Set global_dimension_1 in GL Setup or create BRANCH dimension."
                        )
                    )
                    return

            # 2. Objects - Items table
            item_table = (
                Objects.objects.filter(
                    object_type="Table", related_model="items.Item"
                ).first()
                or Objects._base_manager.filter(
                    object_type="Table", related_model="items.Item"
                ).first()
                or Objects._base_manager.filter(
                    object_type="Table", related_model__iexact="items.item"
                ).first()
            )
            if not item_table:
                self.stdout.write(
                    self.style.ERROR(
                        "Items table not found in Objects. Run: tenant_command populate_objects_table"
                    )
                )
                return
            self.stdout.write(f"Items table: {item_table.object_name} (id={item_table.object_id})")

            # 3. DefaultDimensions per branch
            branches = DimensionValue.objects.filter(
                dimension_code_id=branch_dim_id
            ).order_by("code")
            self.stdout.write(f"\nDefaultDimensions per branch (dimension_code_id={branch_dim_id}):")
            for b in branches:
                count = DefaultDimension.objects.filter(
                    table=item_table,
                    dimension_code_id=branch_dim_id,
                    dimension_value_id=b.id,
                ).count()
                self.stdout.write(f"  {b.code}: {count} items")

            # 4. Items without DefaultDimension for any branch
            from items.models import Item
            item_nos = set(Item.objects.values_list("no", flat=True))
            dd_nos = set(
                DefaultDimension.objects.filter(
                    table=item_table, dimension_code_id=branch_dim_id
                ).values_list("no", flat=True)
            )
            missing = item_nos - dd_nos
            if missing:
                self.stdout.write(
                    self.style.WARNING(
                        f"\nItems WITHOUT branch DefaultDimension: {len(missing)} items"
                    )
                )
                self.stdout.write(
                    f"  Examples: {list(missing)[:5]}{'...' if len(missing) > 5 else ''}"
                )
                self.stdout.write(
                    "  Run: tenant_command seed_item_branch_dimensions --schema=<schema>"
                )
            else:
                self.stdout.write(self.style.SUCCESS("\nAll items have branch DefaultDimension."))

            self.stdout.write("\n")

        if schema_name and schema_context:
            with schema_context(schema_name):
                run()
        else:
            run()
