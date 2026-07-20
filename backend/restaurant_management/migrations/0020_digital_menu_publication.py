# Generated manually for Digital Menu (guest QR menu with images)

import django.db.models.deletion
import utils.utils
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("restaurant_management", "0019_restaurantorderitem_started_at"),
    ]

    operations = [
        migrations.CreateModel(
            name="DigitalMenuPublication",
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
                    "slug",
                    models.SlugField(
                        default="main",
                        help_text="URL segment, e.g. /menu or /menu/{slug}",
                        max_length=64,
                        unique=True,
                        verbose_name="Slug",
                    ),
                ),
                ("title", models.CharField(max_length=200, verbose_name="Title")),
                (
                    "tagline",
                    models.CharField(
                        blank=True, default="", max_length=300, verbose_name="Tagline"
                    ),
                ),
                (
                    "phones",
                    models.JSONField(
                        blank=True, default=list, verbose_name="Phone numbers"
                    ),
                ),
                (
                    "social_links",
                    models.JSONField(
                        blank=True, default=dict, verbose_name="Social links"
                    ),
                ),
                (
                    "brand_primary",
                    models.CharField(
                        default="#3B1614", max_length=20, verbose_name="Brand primary"
                    ),
                ),
                (
                    "brand_accent",
                    models.CharField(
                        default="#E86E25", max_length=20, verbose_name="Brand accent"
                    ),
                ),
                (
                    "currency_code",
                    models.CharField(
                        default="UGX", max_length=8, verbose_name="Currency"
                    ),
                ),
                (
                    "is_published",
                    models.BooleanField(default=True, verbose_name="Published"),
                ),
                (
                    "logo_url",
                    models.CharField(
                        blank=True, default="", max_length=500, verbose_name="Logo URL"
                    ),
                ),
                (
                    "cover_image_url",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=500,
                        verbose_name="Cover image URL",
                    ),
                ),
                (
                    "gallery_images",
                    models.JSONField(
                        blank=True, default=list, verbose_name="Gallery images"
                    ),
                ),
            ],
            options={
                "verbose_name": "Digital menu publication",
                "verbose_name_plural": "Digital menu publications",
                "ordering": ["title"],
            },
        ),
        migrations.CreateModel(
            name="DigitalMenuSection",
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
                    "name",
                    models.CharField(max_length=120, verbose_name="Section name"),
                ),
                (
                    "subtitle",
                    models.CharField(
                        blank=True, default="", max_length=300, verbose_name="Subtitle"
                    ),
                ),
                (
                    "display_order",
                    models.PositiveIntegerField(
                        default=0, verbose_name="Display order"
                    ),
                ),
                (
                    "accent_color",
                    models.CharField(
                        blank=True,
                        default="#FACC15",
                        max_length=20,
                        verbose_name="Accent color",
                    ),
                ),
                (
                    "image_url",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=500,
                        verbose_name="Section image URL",
                    ),
                ),
                (
                    "publication",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sections",
                        to="restaurant_management.digitalmenupublication",
                    ),
                ),
            ],
            options={
                "verbose_name": "Digital menu section",
                "verbose_name_plural": "Digital menu sections",
                "ordering": ["display_order", "name"],
                "unique_together": {("publication", "name")},
            },
        ),
        migrations.CreateModel(
            name="DigitalMenuLine",
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
                ("name", models.CharField(max_length=200, verbose_name="Item name")),
                (
                    "description",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=500,
                        verbose_name="Description",
                    ),
                ),
                (
                    "price",
                    models.DecimalField(
                        decimal_places=2, max_digits=12, verbose_name="Price"
                    ),
                ),
                (
                    "price_note",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text='e.g. "@" for per-piece pricing',
                        max_length=80,
                        verbose_name="Price note",
                    ),
                ),
                (
                    "is_featured",
                    models.BooleanField(default=False, verbose_name="Featured"),
                ),
                (
                    "display_order",
                    models.PositiveIntegerField(
                        default=0, verbose_name="Display order"
                    ),
                ),
                (
                    "section",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lines",
                        to="restaurant_management.digitalmenusection",
                    ),
                ),
            ],
            options={
                "verbose_name": "Digital menu line",
                "verbose_name_plural": "Digital menu lines",
                "ordering": ["display_order", "name"],
            },
        ),
    ]
