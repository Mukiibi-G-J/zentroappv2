from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("company", "0013_add_user_limit_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="billingexpiryreminder",
            name="reminder_key",
            field=models.CharField(
                default="expiry_10_day",
                help_text="Reminder variant key (e.g. expiry_10_day, migration_14_day)",
                max_length=50,
            ),
        ),
    ]
