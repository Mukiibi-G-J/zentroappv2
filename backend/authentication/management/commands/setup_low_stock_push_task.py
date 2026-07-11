"""
Setup Celery Beat periodic task for low-stock mobile push alerts.
Run: python manage.py setup_low_stock_push_task
"""
from django.core.management.base import BaseCommand
from django_celery_beat.models import CrontabSchedule, PeriodicTask


class Command(BaseCommand):
    help = "Setup send_low_stock_push_alerts Celery Beat task (daily 8:00 AM UTC)"

    def handle(self, *args, **options):
        schedule, _ = CrontabSchedule.objects.get_or_create(
            minute="0",
            hour="8",
            day_of_week="*",
            day_of_month="*",
            month_of_year="*",
            timezone="UTC",
        )

        task, created = PeriodicTask.objects.update_or_create(
            name="Low stock mobile push alerts",
            defaults={
                "task": "authentication.tasks.send_low_stock_push_alerts",
                "crontab": schedule,
                "enabled": True,
            },
        )

        verb = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} periodic task: Low stock mobile push alerts (daily 8:00 AM UTC)"
            )
        )
