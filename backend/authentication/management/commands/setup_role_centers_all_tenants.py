"""
Management command to set up default role centers for ALL existing tenants
Run this once to add role centers to all companies that already exist
"""

from django.core.management.base import BaseCommand
from django.core.management import call_command
from company.models import Company
from django.db import connection
from django_tenants.utils import schema_context


class Command(BaseCommand):
    help = "Set up default role centers for all existing tenants"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without making changes",
        )

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(
            self.style.SUCCESS("Setting up Role Centers for ALL Existing Tenants")
        )
        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No changes will be made")
            )
        self.stdout.write("=" * 70 + "\n")

        # Get all companies from public schema
        with schema_context("public"):
            companies = Company.objects.all().order_by("name")
            total_companies = companies.count()

            self.stdout.write(f"Found {total_companies} companies\n")

            success_count = 0
            error_count = 0

            for idx, company in enumerate(companies, 1):
                self.stdout.write(
                    f"[{idx}/{total_companies}] Processing: {company.name} ({company.schema_name})"
                )
                self.stdout.write("-" * 70)

                if dry_run:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  Would setup role centers for: {company.name}"
                        )
                    )
                    success_count += 1
                    self.stdout.write()
                    continue

                try:
                    # Switch to tenant schema
                    connection.set_tenant(company)

                    # Run the setup command
                    call_command("setup_default_role_centers", verbosity=0)

                    success_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f"  ✅ Success: {company.name}")
                    )

                except Exception as e:
                    error_count += 1
                    self.stdout.write(
                        self.style.ERROR(f"  ❌ Error for {company.name}: {str(e)}")
                    )

                self.stdout.write()

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("SUMMARY"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"Total Companies: {total_companies}")
        self.stdout.write(f"Success: {success_count}")
        self.stdout.write(f"Errors: {error_count}")
        self.stdout.write("=" * 70)

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "\n⚠️  DRY RUN - No changes were made. Remove --dry-run to apply."
                )
            )
        elif success_count == total_companies:
            self.stdout.write(
                self.style.SUCCESS("\n✅ All companies now have default role centers!")
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"\n⚠️  {error_count} companies had errors. Check logs above."
                )
            )

        self.stdout.write("\nNext Steps:")
        self.stdout.write(
            "1. Go to Admin Panel: http://TENANT.localhost:8000/admin/authentication/rolecenter/"
        )
        self.stdout.write("2. Verify role centers are created")
        self.stdout.write("3. Assign roles to users")
        self.stdout.write("4. Users will automatically get the correct modules!")
        self.stdout.write("=" * 70 + "\n")
