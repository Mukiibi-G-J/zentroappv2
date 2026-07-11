from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("company", "0015_company_schema_name_unique"),
    ]

    operations = [
        migrations.AddField(
            model_name="company",
            name="grace_reminder_offsets",
            field=models.JSONField(
                blank=True,
                help_text="Optional list of ints: days after due date to send grace reminders (0 = due date). Null = one reminder per day for each day in the grace window (0 .. grace_days-1).",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="company",
            name="subscription_grace_days",
            field=models.PositiveSmallIntegerField(
                default=2,
                help_text="Days after the payment due date before tenant API access is locked (402). Due date is the day after the last day of the current trial or paid period.",
            ),
        ),
    ]
