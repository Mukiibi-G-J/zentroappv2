"""
Backfill enabled_modules for all existing companies.

Uses the Company.compute_enabled_modules() method which maps subscription plan
names to Pricing records and combines with module_overrides.
"""

from django.core.management.base import BaseCommand
from django_tenants.utils import schema_context


class Command(BaseCommand):
    help = "Recompute enabled_modules for all companies based on their subscription plan + overrides"

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant",
            type=str,
            help="Only backfill a specific tenant by schema name",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would change without saving",
        )

    def handle(self, *args, **options):
        with schema_context("public"):
            from company.models import Company, Subscription

            if options["tenant"]:
                companies = Company.objects.filter(schema_name=options["tenant"])
            else:
                companies = Company.objects.exclude(schema_name="public")

            total = companies.count()
            updated = 0

            for company in companies:
                old_modules = list(company.enabled_modules or [])

                try:
                    sub = Subscription.objects.get(company=company)
                    plan = sub.plan or "(empty)"
                    status = sub.status
                except Subscription.DoesNotExist:
                    plan = "N/A"
                    status = "N/A"

                if options["dry_run"]:
                    plan_key = sub.plan if 'sub' in dir() else ""
                    pricing_name = Company.PLAN_NAME_TO_PRICING.get(
                        plan_key or "", plan_key or ""
                    )
                    self.stdout.write(
                        f"  {company.schema_name}: plan={plan}, "
                        f"status={status}, maps_to={pricing_name}, "
                        f"current_modules={old_modules}"
                    )
                else:
                    company.compute_enabled_modules()
                    company.refresh_from_db(fields=["enabled_modules"])
                    new_modules = list(company.enabled_modules or [])

                    if set(old_modules) != set(new_modules):
                        updated += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"  {company.schema_name}: plan={plan} -> "
                                f"{len(new_modules)} modules "
                                f"(was {len(old_modules)})"
                            )
                        )
                    else:
                        self.stdout.write(
                            f"  {company.schema_name}: unchanged "
                            f"({len(new_modules)} modules)"
                        )

            if options["dry_run"]:
                self.stdout.write(
                    self.style.WARNING(f"\nDry run: {total} companies inspected")
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\nDone: {updated}/{total} companies updated"
                    )
                )
