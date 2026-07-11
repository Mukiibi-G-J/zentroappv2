"""
Assign a BRANCH dimension value to all items as default dimensions.

Run: python manage.py tenant_command seed_item_branch_dimensions --schema=<schema> [--branch=<code>]
Or: python manage.py seed_item_branch_dimensions --schema=<schema> [--branch=<code>]

If --branch is not specified, uses the first BRANCH dimension value found.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

try:
    from django_tenants.utils import schema_context
except ImportError:
    schema_context = None


class Command(BaseCommand):
    help = "Assign a BRANCH dimension value as default dimension to all items"

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            type=str,
            default=None,
            help="Tenant schema name. Required for multi-tenant. Use tenant_command for tenant-specific run.",
        )
        parser.add_argument(
            "--branch",
            type=str,
            default=None,
            help="Dimension value code (e.g. NTINDA, KYANJA). If omitted, uses first BRANCH value.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without making changes.",
        )

    def handle(self, *args, **options):
        schema_name = options.get("schema")
        branch_code = options.get("branch")
        dry_run = options.get("dry_run", False)

        if schema_name and schema_context is None:
            self.stdout.write(
                self.style.WARNING("django-tenants not installed; ignoring --schema")
            )
            schema_name = None

        def run():
            from base.models import Objects
            from dimension.models import DefaultDimension, Dimension, DimensionValue
            from items.models import Item

            # 1. Get Items table object
            table_obj = Objects.objects.filter(
                object_type="Table", related_model="items.Item"
            ).first()
            if not table_obj:
                self.stdout.write(
                    self.style.ERROR(
                        "Items table not found in Objects. Run: python manage.py tenant_command populate_objects_table --schema=<schema>"
                    )
                )
                return

            # 2. Get BRANCH dimension
            branch_dim = Dimension.objects.filter(code__iexact="BRANCH").first()
            if not branch_dim:
                self.stdout.write(
                    self.style.ERROR(
                        "BRANCH dimension not found. Create it under Dimension → Dimensions."
                    )
                )
                return

            # 3. Get branch dimension value
            if branch_code:
                dim_value = DimensionValue.objects.filter(
                    dimension_code=branch_dim, code__iexact=branch_code
                ).first()
                if not dim_value:
                    self.stdout.write(
                        self.style.ERROR(
                            f"Dimension value '{branch_code}' not found for BRANCH. "
                            f"Available: {list(DimensionValue.objects.filter(dimension_code=branch_dim).values_list('code', flat=True))}"
                        )
                    )
                    return
            else:
                dim_value = (
                    DimensionValue.objects.filter(dimension_code=branch_dim)
                    .order_by("code")
                    .first()
                )
                if not dim_value:
                    self.stdout.write(
                        self.style.ERROR(
                            "No BRANCH dimension values found. Create them under Dimension → Dimension Values."
                        )
                    )
                    return

            items = Item.objects.all().values_list("no", flat=True)
            count = len(items)
            if count == 0:
                self.stdout.write(self.style.WARNING("No items found."))
                return

            if dry_run:
                self.stdout.write(
                    f"[DRY RUN] Would assign BRANCH={dim_value.code} to {count} items: {list(items)[:10]}{'...' if count > 10 else ''}"
                )
                return

            created = 0
            updated = 0
            for item_no in items:
                obj, was_created = DefaultDimension.objects.update_or_create(
                    table=table_obj,
                    no=str(item_no),
                    dimension_code=branch_dim,
                    defaults={
                        "dimension_value": dim_value,
                        "value_posting": DefaultDimension.ValuePosting.NONE,
                    },
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

            self.stdout.write(
                self.style.SUCCESS(
                    f"Assigned BRANCH={dim_value.code} to all items: {created} created, {updated} updated."
                )
            )

        if schema_name:
            with schema_context(schema_name):
                with transaction.atomic():
                    run()
        else:
            with transaction.atomic():
                run()
