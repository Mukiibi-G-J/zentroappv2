"""
Setup Celery Beat periodic task for billing expiry 10-day reminder emails.
Run: python manage.py setup_billing_expiry_reminder_task
"""
from django.core.management.base import BaseCommand
from django_celery_beat.models import CrontabSchedule, PeriodicTask


class Command(BaseCommand):
    help = "Setup the send_billing_expiry_10day_reminders Celery Beat periodic task (daily at 8:00 AM UTC)"

    def handle(self, *args, **options):
        # Create or get crontab: 8:00 AM daily
        schedule, _ = CrontabSchedule.objects.get_or_create(
            minute="0",
            hour="8",
            day_of_week="*",
            day_of_month="*",
            month_of_year="*",
            timezone="UTC",
        )

        task, created = PeriodicTask.objects.update_or_create(
            name="Send billing expiry 10-day reminders",
            defaults={
                "task": "company.tasks.send_billing_expiry_10day_reminders",
                "crontab": schedule,
                "enabled": True,
            },
        )

        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    "Created periodic task: Send billing expiry 10-day reminders (daily 8:00 AM UTC)"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "Updated periodic task: Send billing expiry 10-day reminders (daily 8:00 AM UTC)"
                )
            )
