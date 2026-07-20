"""
Seed customer-facing digital menu (NOT the POS Menu model).

Usage:
  python manage.py tenant_command seed_digital_menu --schema=thestormscafe
  python manage.py tenant_command seed_digital_menu --schema=thestormscafe --clear
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django_tenants.utils import schema_context

from restaurant_management.data.storms_cafe_menu import (
    DIGITAL_MENU_PUBLICATION_IMAGES,
    DIGITAL_MENU_SECTION_IMAGES,
    DIGITAL_MENU_SECTION_SUBTITLES,
    DISPLAY_GROUPS,
    build_catalog,
)
from restaurant_management.models import (
    DigitalMenuLine,
    DigitalMenuPublication,
    DigitalMenuSection,
)


def _price_note(description: str) -> str:
    d = (description or "").lower()
    if "per piece" in d:
        return "@"
    return ""


@transaction.atomic
def seed_digital_menu(*, catalog_key: str = "storms", clear: bool = False) -> dict:
    if catalog_key != "storms":
        raise ValueError(f"Unknown catalog: {catalog_key}")

    catalog = build_catalog()
    restaurant = catalog["restaurant"]
    group_colors = {g["name"]: g.get("tile_color", "#FACC15") for g in DISPLAY_GROUPS}

    summary = {
        "publication": None,
        "sections": 0,
        "lines": 0,
    }

    if clear:
        DigitalMenuLine.objects.all().delete()
        DigitalMenuSection.objects.all().delete()
        DigitalMenuPublication.objects.all().delete()

    pub, _ = DigitalMenuPublication.objects.update_or_create(
        slug="main",
        defaults={
            "title": restaurant["name"],
            "tagline": restaurant.get("tagline", ""),
            "phones": restaurant.get("phones", []),
            "social_links": {
                "facebook": "",
                "instagram": "",
                "tiktok": "",
                "x": "",
            },
            "brand_primary": "#3B1614",
            "brand_accent": "#E86E25",
            "currency_code": "UGX",
            "is_published": True,
            "logo_url": DIGITAL_MENU_PUBLICATION_IMAGES["logo_url"],
            "cover_image_url": DIGITAL_MENU_PUBLICATION_IMAGES["cover_image_url"],
            "gallery_images": DIGITAL_MENU_PUBLICATION_IMAGES["gallery_images"],
        },
    )
    summary["publication"] = pub.slug

    section_map: dict[str, DigitalMenuSection] = {}
    group_order = {g["name"]: g["display_order"] for g in DISPLAY_GROUPS}

    for group_name in sorted(group_order, key=lambda n: group_order[n]):
        section, _ = DigitalMenuSection.objects.update_or_create(
            publication=pub,
            name=group_name,
            defaults={
                "display_order": group_order[group_name],
                "accent_color": group_colors.get(group_name, "#FACC15"),
                "image_url": DIGITAL_MENU_SECTION_IMAGES.get(group_name, ""),
                "subtitle": DIGITAL_MENU_SECTION_SUBTITLES.get(group_name, ""),
            },
        )
        section_map[group_name] = section
        summary["sections"] += 1

    lines_by_section: dict[str, list] = defaultdict(list)
    line_order = 0
    for cat in catalog["categories"]:
        group = cat.get("display_group") or cat["name"]
        for item in cat.get("items", []):
            line_order += 10
            desc = (item.get("description") or "").strip()
            lines_by_section[group].append(
                {
                    "name": item["item_name"],
                    "description": desc,
                    "price": Decimal(str(item["unit_price"])),
                    "price_note": _price_note(desc),
                    "is_featured": bool(item.get("is_featured")),
                    "display_order": line_order,
                }
            )

    if clear:
        DigitalMenuLine.objects.filter(section__publication=pub).delete()

    for group_name, lines in lines_by_section.items():
        section = section_map.get(group_name)
        if not section:
            section, _ = DigitalMenuSection.objects.get_or_create(
                publication=pub,
                name=group_name,
                defaults={"display_order": 99, "accent_color": "#FACC15"},
            )
            section_map[group_name] = section

        for line_data in lines:
            DigitalMenuLine.objects.update_or_create(
                section=section,
                name=line_data["name"],
                defaults=line_data,
            )
            summary["lines"] += 1

    return summary


class Command(BaseCommand):
    help = "Seed public digital menu (guest QR menu — not POS Menu)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant",
            "--schema",
            dest="tenant",
            type=str,
            help="Tenant schema name (use with tenant_command).",
        )
        parser.add_argument(
            "--catalog",
            type=str,
            default="storms",
            help="Catalog preset (storms = The Storms Cafe)",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Remove existing digital menu data before seeding",
        )

    def handle(self, *args, **options):
        tenant = options.get("tenant")

        def run():
            summary = seed_digital_menu(
                catalog_key=options["catalog"],
                clear=options["clear"],
            )
            label = tenant or "current schema"
            self.stdout.write(
                self.style.SUCCESS(
                    f"Digital menu seeded for {label}: "
                    f"publication={summary['publication']}, "
                    f"sections={summary['sections']}, lines={summary['lines']}"
                )
            )

        if tenant:
            with schema_context(tenant):
                run()
        else:
            run()
