from django.core.management.base import BaseCommand
from django.utils import timezone
from company.models import ZentroStarterOrder, ZentroStarterOffer, Subscription


class Command(BaseCommand):
    help = "Update existing starter pack orders from 3 months to 12 months free period"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without actually updating',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No changes will be made")
            )

        # Find all orders with free_months_earned = 3
        orders_to_update = ZentroStarterOrder.objects.filter(free_months_earned=3)
        
        self.stdout.write(
            self.style.SUCCESS(
                f"Found {orders_to_update.count()} orders with free_months_earned=3"
            )
        )

        updated_count = 0
        skipped_count = 0

        for order in orders_to_update:
            try:
                # Calculate new dates based on 12 months instead of 3
                if order.subscription_start_date:
                    # If subscription is already activated, recalculate dates
                    start_date = order.subscription_start_date
                    
                    # Calculate new free period end date (12 months from start)
                    new_free_period_end = start_date + timezone.timedelta(days=12 * 30)
                    
                    # Only update if the new end date is in the future
                    # and if the subscription hasn't ended yet
                    if new_free_period_end > timezone.now() and (
                        not order.free_period_end_date or 
                        timezone.now() < order.free_period_end_date
                    ):
                        if not dry_run:
                            order.free_months_earned = 12
                            order.free_period_end_date = new_free_period_end
                            order.subscription_end_date = new_free_period_end
                            order.save()
                            
                            # Also update the Subscription model
                            try:
                                subscription = Subscription.objects.get(company=order.company)
                                subscription.subscription_end_date = new_free_period_end.date()
                                subscription.trial_period_end_date = new_free_period_end.date()
                                subscription.save()
                                self.stdout.write(
                                    f"  [OK] Updated order {order.id} for company {order.company.name} - "
                                    f"New end date: {new_free_period_end.date()}"
                                )
                            except Subscription.DoesNotExist:
                                self.stdout.write(
                                    self.style.WARNING(
                                        f"  [WARN] Order {order.id} updated but Subscription not found for company {order.company.name}"
                                    )
                                )
                        else:
                            self.stdout.write(
                                f"  [DRY RUN] Would update order {order.id} for company {order.company.name} - "
                                f"New end date: {new_free_period_end.date()}"
                            )
                        updated_count += 1
                    else:
                        self.stdout.write(
                            self.style.WARNING(
                                f"  [SKIP] Skipped order {order.id} - subscription already ended or dates are in the past"
                            )
                        )
                        skipped_count += 1
                else:
                    # Order not activated yet, just update free_months_earned
                    # The dates will be calculated correctly when activated
                    if not dry_run:
                        order.free_months_earned = 12
                        order.save()
                        self.stdout.write(
                            f"  [OK] Updated order {order.id} for company {order.company.name} - "
                            f"free_months_earned set to 12 (will use when activated)"
                        )
                    else:
                        self.stdout.write(
                            f"  [DRY RUN] Would update order {order.id} for company {order.company.name} - "
                            f"free_months_earned to 12"
                        )
                    updated_count += 1

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"  [ERROR] Error updating order {order.id}: {str(e)}"
                    )
                )

        # Also update offers that still have free_months = 3
        offers_to_update = ZentroStarterOffer.objects.filter(free_months=3)
        offers_count = offers_to_update.count()
        
        if offers_count > 0:
            if not dry_run:
                offers_to_update.update(free_months=12)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Updated {offers_count} offers from free_months=3 to free_months=12"
                    )
                )
            else:
                self.stdout.write(
                    f"[DRY RUN] Would update {offers_count} offers from free_months=3 to free_months=12"
                )

        # Summary
        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"\n[SUMMARY]\n"
                f"  Orders updated: {updated_count}\n"
                f"  Orders skipped: {skipped_count}\n"
                f"  Offers updated: {offers_count if not dry_run else offers_count}\n"
            )
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "\nThis was a dry run. Run without --dry-run to apply changes."
                )
            )

