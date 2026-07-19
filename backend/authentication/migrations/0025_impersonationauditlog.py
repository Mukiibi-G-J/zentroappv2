# Generated manually for ImpersonationAuditLog

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0024_customuser_must_change_password"),
    ]

    operations = [
        migrations.CreateModel(
            name="ImpersonationAuditLog",
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
                    models.CharField(
                        db_index=True,
                        default=uuid.uuid4,
                        editable=False,
                        max_length=36,
                        unique=True,
                        verbose_name="System ID",
                    ),
                ),
                ("actor_id", models.IntegerField(db_index=True)),
                ("actor_username", models.CharField(max_length=255)),
                ("target_id", models.IntegerField(db_index=True)),
                ("target_username", models.CharField(max_length=255)),
                ("started_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "ended_at",
                    models.DateTimeField(blank=True, db_index=True, null=True),
                ),
                (
                    "ip_address",
                    models.GenericIPAddressField(blank=True, null=True),
                ),
                (
                    "user_agent",
                    models.CharField(blank=True, default="", max_length=512),
                ),
            ],
            options={
                "verbose_name": "Impersonation Audit Log",
                "verbose_name_plural": "Impersonation Audit Logs",
                "ordering": ["-started_at"],
            },
        ),
    ]
