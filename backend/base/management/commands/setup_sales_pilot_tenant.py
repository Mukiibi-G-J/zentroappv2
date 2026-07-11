from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import connection
from company.models import Company


class Command(BaseCommand):
    help = "Setup Sales Permission Pilot for a specific tenant"

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            type=str,
            default="ekk",
            help="Tenant schema name (default: ekk)",
        )

    def handle(self, *args, **options):
        schema_name = options["schema"]

        try:
            # Get tenant (use first() in case there are duplicates)
            tenant = Company.objects.filter(schema_name=schema_name).first()
            if not tenant:
                self.stdout.write(
                    self.style.ERROR(f"❌ Tenant '{schema_name}' not found!")
                )
                return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error getting tenant: {str(e)}"))
            return

        # Switch to tenant schema
        connection.set_tenant(tenant)

        self.stdout.write(
            self.style.SUCCESS(
                f"\n🏢 Setting up Sales Pilot for: {tenant.name} ({tenant.schema_name})"
            )
        )
        self.stdout.write("=" * 70)

        try:
            # Step 1: Setup Sales Permissions
            self.stdout.write("\n🔐 Step 1: Setting up Sales Permissions...")
            call_command("setup_sales_permissions")

            # Step 2: Create Sales User Groups
            self.stdout.write("\n👥 Step 2: Creating Sales User Groups...")
            call_command("create_sales_groups")

            # Summary
            self.stdout.write("\n" + "=" * 70)
            self.stdout.write(
                self.style.SUCCESS(f"✅ Sales Pilot Setup Complete for {tenant.name}!")
            )

            self.stdout.write("\n💡 Next Steps:")
            self.stdout.write(
                f"  1. Visit: http://{tenant.schema_name}.localhost:8000/admin/"
            )
            self.stdout.write("  2. Go to: Authentication > User Groups")
            self.stdout.write("  3. Add users to the appropriate groups:")
            self.stdout.write("     • Sales - Cashiers (for cashiers)")
            self.stdout.write("     • Sales Team (for sales reps)")
            self.stdout.write("     • Sales - Viewers (for read-only users)")
            self.stdout.write("  4. Test permissions!")
            self.stdout.write("")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n❌ Error during setup: {str(e)}"))
            import traceback

            traceback.print_exc()
