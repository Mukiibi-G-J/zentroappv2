"""
Setup Celery Beat periodic task for trial-end reminder emails.
Run: python manage.py setup_trial_reminder_task
"""
from django.core.management.base import BaseCommand
from django_celery_beat.models import CrontabSchedule, PeriodicTask


class Command(BaseCommand):
    help = "Setup the send_trial_end_reminders Celery Beat periodic task (daily at 9:00 AM)"

    def handle(self, *args, **options):
        # Create or get crontab: 9:00 AM daily
        schedule, _ = CrontabSchedule.objects.get_or_create(
            minute="0",
            hour="9",
            day_of_week="*",
            day_of_month="*",
            month_of_year="*",
            timezone="UTC",
        )

        task, created = PeriodicTask.objects.update_or_create(
            name="Send trial-end reminders",
            defaults={
                "task": "company.tasks.send_trial_end_reminders",
                "crontab": schedule,
                "enabled": True,
            },
        )

        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    "Created periodic task: Send trial-end reminders (daily 9:00 AM UTC)"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "Updated periodic task: Send trial-end reminders (daily 9:00 AM UTC)"
                )
            )
