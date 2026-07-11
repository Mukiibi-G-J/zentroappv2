# Generated manually - Add DimensionSet and DimensionSetEntry (BC Table 480 equivalent)

import uuid
from django.db import migrations, models
import django.db.models.deletion
import utils.utils


class Migration(migrations.Migration):

    dependencies = [
        ("dimension", "0003_dimension_id_pk"),
    ]

    operations = [
        migrations.CreateModel(
            name="DimensionSet",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Updated At")),
                ("system_id", utils.utils.UUIField(db_index=True, default=uuid.uuid4, editable=False, max_length=36, unique=True, verbose_name="System ID")),
                ("signature", models.CharField(blank=True, db_index=True, max_length=64, null=True, unique=True)),
            ],
            options={
                "verbose_name": "Dimension Set",
                "verbose_name_plural": "Dimension Sets",
            },
        ),
        migrations.CreateModel(
            name="DimensionSetEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Updated At")),
                ("system_id", utils.utils.UUIField(db_index=True, default=uuid.uuid4, editable=False, max_length=36, unique=True, verbose_name="System ID")),
                (
                    "dimension_set",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="entries",
                        to="dimension.dimensionset",
                    ),
                ),
                (
                    "dimension_code",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="dimension_set_entries",
                        to="dimension.dimension",
                    ),
                ),
                (
                    "dimension_value",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="dimension_set_entries",
                        to="dimension.dimensionvalue",
                    ),
                ),
            ],
            options={
                "verbose_name": "Dimension Set Entry",
                "verbose_name_plural": "Dimension Set Entries",
                "unique_together": {("dimension_set", "dimension_code")},
            },
        ),
    ]
