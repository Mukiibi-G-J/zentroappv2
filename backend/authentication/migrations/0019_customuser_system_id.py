import uuid

from django.db import migrations, models
import utils.utils


def backfill_system_ids(apps, schema_editor):
    """Assign a distinct system_id to every existing user (Postgres cannot use one default for all rows)."""
    CustomUser = apps.get_model("authentication", "CustomUser")
    for user in CustomUser.objects.all().iterator():
        user.system_id = str(uuid.uuid4())
        user.save(update_fields=["system_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0018_devicepushtoken"),
    ]

    operations = [
        # Use plain CharField — UUIField always forces unique=True and would backfill
        # every row with the same default UUID on PostgreSQL.
        migrations.AddField(
            model_name="customuser",
            name="system_id",
            field=models.CharField(
                max_length=36,
                null=True,
                editable=False,
            ),
        ),
        migrations.RunPython(backfill_system_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="customuser",
            name="system_id",
            field=utils.utils.UUIField(
                db_index=True,
                default=uuid.uuid4,
                editable=False,
                max_length=36,
                unique=True,
                verbose_name="System ID",
            ),
        ),
    ]
