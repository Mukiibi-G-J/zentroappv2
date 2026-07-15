from django.core.management.base import BaseCommand
from base.models import Objects, ObjectType


class Command(BaseCommand):
    help = "Register Sales module tables as objects (PILOT)"

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS("\n🔐 Registering Sales Module Objects...\n")
        )

        # Get or create Table object type (lookup by unique code, not name)
        table_obj_type, created = ObjectType.objects.get_or_create(
            code="TABLE",
            defaults={
                "name": "Table",
                "description": "Database tables",
                "sort_order": 1,
            },
        )

        if created:
            self.stdout.write("  ✓ Created ObjectType: Table")
        else:
            self.stdout.write("  ℹ️  Using existing ObjectType: Table")

        # Sales module tables - ID range 2600-2799
        SALES_TABLES = [
            (2600, "Customer", "sales.Customer"),
            (2610, "Customer Ledger Entry", "sales.CustomerLedgerEntry"),
            (2700, "Sales Invoice", "sales.SalesInvoice"),
            (2710, "Sales Invoice Line", "sales.SalesInvoiceLine"),
            (2720, "Sales Receivable Setup", "sales.SalesReceivable"),
        ]

        created_count = 0
        updated_count = 0

        self.stdout.write("\n📊 Registering Sales Tables:")
        self.stdout.write("=" * 70)

        for object_id, object_name, related_model in SALES_TABLES:
            obj, created = Objects.objects.update_or_create(
                object_id=object_id,
                defaults={
                    "object_type_ref": table_obj_type,
                    "object_name": object_name,
                    "requires_permission": True,
                    "related_model": related_model,
                },
            )

            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"  ✓ Created: {object_name} (ID: {object_id})")
                )
            else:
                updated_count += 1
                self.stdout.write(f"  🔄 Updated: {object_name} (ID: {object_id})")

        # Summary
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("✅ Sales objects registration complete!"))
        self.stdout.write(f"\n📝 Created: {created_count} objects")
        self.stdout.write(f"🔄 Updated: {updated_count} objects")
        self.stdout.write(f"📊 Total Sales Objects: {len(SALES_TABLES)}")

        self.stdout.write("\n💡 Next Steps:")
        self.stdout.write("  1. Run: python manage.py setup_sales_permissions")
        self.stdout.write("  2. Run: python manage.py create_sales_groups")
        self.stdout.write(
            "  3. Visit admin to verify: http://ekk.localhost:8000/admin/base/objects/\n"
        )
