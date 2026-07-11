# Generated manually for DevicePushToken

import uuid

import django.db.models.deletion
import utils.utils
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0017_usersetup_can_reverse_item_journal"),
    ]

    operations = [
        migrations.CreateModel(
            name="DevicePushToken",
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
                        verbose_name="System ID",
                    ),
                ),
                ("device_id", models.CharField(db_index=True, max_length=128)),
                ("fcm_token", models.TextField()),
                ("platform", models.CharField(default="android", max_length=16)),
                ("is_active", models.BooleanField(default=True)),
                ("last_seen_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="device_push_tokens",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Device push token",
                "verbose_name_plural": "Device push tokens",
                "db_table": "authentication_devicepushtoken",
            },
        ),
        migrations.AddIndex(
            model_name="devicepushtoken",
            index=models.Index(
                fields=["user", "is_active"], name="auth_devpush_user_active_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="devicepushtoken",
            index=models.Index(
                fields=["fcm_token"], name="auth_devpush_fcm_token_idx"
            ),
        ),
        migrations.AddConstraint(
            model_name="devicepushtoken",
            constraint=models.UniqueConstraint(
                fields=("user", "device_id"),
                name="uniq_device_push_token_user_device",
            ),
        ),
    ]
