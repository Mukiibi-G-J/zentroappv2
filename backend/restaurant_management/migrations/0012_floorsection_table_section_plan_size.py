import uuid

import django.db.models.deletion
import utils.utils
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("restaurant_management", "0011_floor_location"),
    ]

    operations = [
        migrations.CreateModel(
            name="FloorSection",
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
                ("name", models.CharField(max_length=100, verbose_name="Section name")),
                (
                    "display_order",
                    models.IntegerField(default=0, verbose_name="Display order"),
                ),
                (
                    "floor",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sections",
                        to="restaurant_management.floor",
                    ),
                ),
            ],
            options={
                "verbose_name": "Floor section",
                "verbose_name_plural": "Floor sections",
                "ordering": ["floor", "display_order", "name"],
            },
        ),
        migrations.AddField(
            model_name="table",
            name="plan_height",
            field=models.PositiveSmallIntegerField(
                default=80,
                help_text="Table tile height on floor plan canvas (pixels).",
                verbose_name="Plan height",
            ),
        ),
        migrations.AddField(
            model_name="table",
            name="plan_width",
            field=models.PositiveSmallIntegerField(
                default=80,
                help_text="Table tile width on floor plan canvas (pixels).",
                verbose_name="Plan width",
            ),
        ),
        migrations.AddField(
            model_name="table",
            name="section",
            field=models.ForeignKey(
                blank=True,
                help_text="Optional section grouping (e.g. Bar, Patio).",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="tables",
                to="restaurant_management.floorsection",
            ),
        ),
        migrations.AlterModelOptions(
            name="table",
            options={
                "ordering": ["floor", "section", "table_number"],
                "verbose_name": "Table",
                "verbose_name_plural": "Tables",
            },
        ),
    ]
