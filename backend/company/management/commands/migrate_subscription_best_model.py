"""
Migration command for Subscription Best Model.

Migrates existing companies from Starter Pack flow to Subscription Best:
- 14-day free trial
- Monthly subscriptions from UGX 50,000

Run per tenant: python manage.py tenant_command migrate_subscription_best_model --schema=<schema>
Run all tenants: python manage.py migrate_schemas --command=migrate_subscription_best_model
"""

from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone
from datetime import timedelta

from company.models import Subscription, ZentroStarterOrder
from company.enums import SubscriptionPlan, SubscriptionStatus


class Command(BaseCommand):
    help = "Migrate company from Starter Pack to Subscription Best model"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be updated without making changes",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No changes will be made")
            )

        # When run via tenant_command, we're in a tenant schema - get current tenant
        tenant = getattr(connection, "tenant", None)
        if not tenant:
            self.stdout.write(
                self.style.ERROR(
                    "No tenant in connection. Run via: "
                    "python manage.py tenant_command migrate_subscription_best_model --schema=<schema>"
                )
            )
            return

        company = tenant
        now = timezone.now().date()
        fourteen_days_from_now = now + timedelta(days=14)
        migrated = 0
        skipped = 0

        try:
            subscription = Subscription.objects.filter(company=company).first()
            if not subscription:
                self.stdout.write(
                    self.style.WARNING(
                        f"  [SKIP] Company {company.name} - no Subscription found"
                    )
                )
                skipped = 1
            else:
                starter_order = (
                    ZentroStarterOrder.objects.filter(
                        company=company,
                        status__in=["paid", "active", "free_period_ended"],
                    )
                    .order_by("-created_at")
                    .first()
                )

                updates = None
                if starter_order:
                    # Company has active starter pack - migrate dates to Subscription
                    if starter_order.is_free_period_active:
                        end_date = (
                            starter_order.free_period_end_date.date()
                            if starter_order.free_period_end_date
                            else fourteen_days_from_now
                        )
                        updates = {
                            "plan": SubscriptionPlan.FREE_TRIAL.value,
                            "status": SubscriptionStatus.TRIAL.value,
                            "trial_period_end_date": end_date,
                            "subscription_end_date": end_date,
                            "is_paid": False,
                            "is_trial": True,
                        }
                        self.stdout.write(
                            f"  [MIGRATE] {company.name}: Starter free period -> "
                            f"trial until {end_date}"
                        )
                    elif starter_order.is_subscription_active:
                        end_date = (
                            starter_order.subscription_end_date.date()
                            if starter_order.subscription_end_date
                            else fourteen_days_from_now
                        )
                        updates = {
                            "plan": SubscriptionPlan.STARTER_PACK.value,
                            "status": SubscriptionStatus.ACTIVE.value,
                            "trial_period_end_date": end_date,
                            "subscription_end_date": end_date,
                            "is_paid": True,
                            "is_trial": False,
                        }
                        self.stdout.write(
                            f"  [MIGRATE] {company.name}: Starter paid period -> "
                            f"active until {end_date}"
                        )
                    else:
                        updates = {
                            "plan": SubscriptionPlan.FREE_TRIAL.value,
                            "status": SubscriptionStatus.TRIAL.value,
                            "trial_period_end_date": now,
                            "subscription_end_date": now,
                            "is_paid": False,
                            "is_trial": False,
                        }
                        self.stdout.write(
                            f"  [MIGRATE] {company.name}: Starter ended -> "
                            "needs monthly subscription"
                        )
                else:
                    existing_end = subscription.trial_period_end_date
                    if existing_end and existing_end > fourteen_days_from_now:
                        updates = {
                            "trial_period_end_date": fourteen_days_from_now,
                            "subscription_end_date": fourteen_days_from_now,
                        }
                        self.stdout.write(
                            f"  [MIGRATE] {company.name}: Cap trial at 14 days "
                            f"(was {existing_end})"
                        )
                    else:
                        self.stdout.write(
                            f"  [SKIP] {company.name}: Trial already within 14 days"
                        )
                        skipped = 1

                if updates and not dry_run:
                    for attr, value in updates.items():
                        setattr(subscription, attr, value)
                    subscription.save()
                    migrated = 1
                elif updates:
                    migrated = 1

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f"  [ERROR] Company {company.name}: {str(e)}"
                )
            )
            skipped = 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\nMigrated: {migrated}, Skipped: {skipped}"
            )
        )
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "Run without --dry-run to apply changes."
                )
            )
