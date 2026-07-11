import django.db.models.deletion
import utils.utils
import uuid
from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


def backfill_pin_set_at(apps, schema_editor):
    CustomUser = apps.get_model("authentication", "CustomUser")
    CustomUser.objects.exclude(
        restaurant_pin_hash__isnull=True,
    ).exclude(restaurant_pin_hash="").filter(
        restaurant_pin_set_at__isnull=True,
    ).update(restaurant_pin_set_at=timezone.now())


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0013_customuser_terminated"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="restaurant_pin_set_at",
            field=models.DateTimeField(
                blank=True,
                help_text="When the restaurant PIN was last set or changed (for rotation / expiry).",
                null=True,
            ),
        ),
        migrations.CreateModel(
            name="RestaurantStaffDevice",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True, db_index=True, verbose_name="Created At"
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="Updated At"),
                ),
                (
                    "system_id",
                    utils.utils.UUIField(
                        db_index=True,
                        default=uuid.uuid4,
                        editable=False,
                        max_length=36,
                        unique=True,
                        verbose_name="System ID",
                    ),
                ),
                (
                    "device_id",
                    models.CharField(
                        db_index=True,
                        help_text="Client-generated stable ID (e.g. UUID).",
                        max_length=64,
                        unique=True,
                    ),
                ),
                ("is_revoked", models.BooleanField(default=False)),
                ("failed_attempts", models.PositiveSmallIntegerField(default=0)),
                ("locked_until", models.DateTimeField(blank=True, null=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="restaurant_staff_devices",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Restaurant staff device",
                "verbose_name_plural": "Restaurant staff devices",
                "db_table": "authentication_restaurantstaffdevice",
            },
        ),
        migrations.RunPython(backfill_pin_set_at, migrations.RunPython.noop),
    ]
