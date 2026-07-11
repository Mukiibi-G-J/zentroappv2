"""
Seed Royal Joint Restaurant menu: POS Items, MenuCategories, MenuItems, Menu, and display groups.

Prerequisites:
  python manage.py tenant_command seed_restaurant_module --schema=YOUR_SCHEMA

Usage:
  python manage.py tenant_command seed_royal_joint_menu --schema=YOUR_SCHEMA
  python manage.py tenant_command seed_royal_joint_menu --schema=YOUR_SCHEMA --dry-run
  python manage.py tenant_command seed_royal_joint_menu --schema=YOUR_SCHEMA --clear

Data source: restaurant_management/data/royal_joint_menu.py
JSON export: data/restaurant/royal_joint_menu.json (run export_royal_joint_menu_json)
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django_tenants.utils import schema_context

from items.enums import InventoryType
from items.models import Item, ItemCategory, ItemUnitOfMeasure, UnitOfMeasure
from postings.models import GeneralProductPostingGroup
from restaurant_management.data.royal_joint_menu import build_catalog
from restaurant_management.models import (
    Menu,
    MenuCategory,
    MenuDisplayGroup,
    MenuItem,
)
from setup.models import InventorySetup, NoSeries, NoSeriesLines


def _price_note(item_data: dict) -> str:
    pmin = item_data.get("price_min")
    pmax = item_data.get("price_max")
    if pmin is not None and pmax is not None and pmin != pmax:
        return f"Menu price: UGX {pmin:,} – {pmax:,} (seeded at UGX {item_data['unit_price']:,})."
    return ""


def _full_description(item_data: dict) -> str:
    parts = []
    base = (item_data.get("description") or "").strip()
    if base:
        parts.append(base)
    note = _price_note(item_data)
    if note:
        parts.append(note)
    return "\n".join(parts)


def _ensure_item_prerequisites(catalog: dict) -> None:
    """Bootstrap minimal inventory setup so POS service items can be created."""
    ic_data = catalog["item_category"]
    ItemCategory.objects.get_or_create(
        code=ic_data["code"],
        defaults={"description": ic_data["description"]},
    )

    uom_code = catalog.get("unit_of_measure", "PCS")
    UnitOfMeasure.objects.get_or_create(
        code=uom_code,
        defaults={"description": "Pieces"},
    )

    GeneralProductPostingGroup.objects.get_or_create(
        code="SERVICE",
        defaults={"description": "Service items", "default": False},
    )

    item_series, _ = NoSeries.objects.get_or_create(
        code="ITM",
        defaults={"description": "Item numbers"},
    )
    if not NoSeriesLines.objects.filter(no_series=item_series).exists():
        NoSeriesLines.objects.create(
            no_series=item_series,
            start_number="ITM-000001",
            increment_by=1,
        )

    if not InventorySetup.objects.exists():
        InventorySetup.objects.create(item_no_series=item_series)


@transaction.atomic
def seed_royal_joint_menu(*, clear: bool = False, dry_run: bool = False) -> dict:
    catalog = build_catalog()
    summary = {
        "items_created": 0,
        "items_updated": 0,
        "menu_items_created": 0,
        "menu_items_updated": 0,
        "categories_created": 0,
        "display_groups_created": 0,
        "skipped": 0,
    }

    if clear and not dry_run:
        menu_code = catalog["menu"]["code"]
        mi_qs = MenuItem.objects.filter(menu__code=menu_code)
        item_ids = list(mi_qs.values_list("item_id", flat=True))
        mi_qs.delete()
        if item_ids:
            Item.objects.filter(pk__in=item_ids).delete()
        MenuDisplayGroup.objects.filter(menu__code=menu_code).delete()
        cat_names = [c["name"] for c in catalog["categories"]]
        MenuCategory.objects.filter(name__in=cat_names).delete()
        Menu.objects.filter(code=menu_code).delete()

    if not dry_run:
        _ensure_item_prerequisites(catalog)

    menu_defaults = {
        "name": catalog["menu"]["name"],
        "is_active": catalog["menu"].get("is_active", True),
    }
    if dry_run:
        menu = None
    else:
        menu, _ = Menu.objects.get_or_create(
            code=catalog["menu"]["code"],
            defaults=menu_defaults,
        )
        for key, val in menu_defaults.items():
            if getattr(menu, key) != val:
                setattr(menu, key, val)
        menu.save()

    ic_data = catalog["item_category"]
    if not dry_run:
        ItemCategory.objects.get_or_create(
            code=ic_data["code"],
            defaults={"description": ic_data["description"]},
        )

    uom_code = catalog.get("unit_of_measure", "PCS")
    if not dry_run:
        uom, _ = UnitOfMeasure.objects.get_or_create(
            code=uom_code,
            defaults={"description": "Pieces"},
        )
    else:
        uom = None

    display_group_by_name: dict[str, MenuDisplayGroup | None] = {}
    for dg in catalog.get("display_groups", []):
        if dry_run:
            display_group_by_name[dg["name"]] = None
            summary["display_groups_created"] += 1
            continue
        obj, created = MenuDisplayGroup.objects.get_or_create(
            menu=menu,
            name=dg["name"],
            defaults={
                "display_order": dg.get("display_order", 0),
                "tile_color": dg.get("tile_color", ""),
                "icon": dg.get("icon", ""),
                "is_active": True,
            },
        )
        if not created:
            obj.display_order = dg.get("display_order", obj.display_order)
            obj.tile_color = dg.get("tile_color", obj.tile_color)
            obj.save()
        else:
            summary["display_groups_created"] += 1
        display_group_by_name[dg["name"]] = obj

    display_order_item = 0
    for cat_data in catalog["categories"]:
        cat_defaults = {
            "name": cat_data["name"],
            "description": cat_data.get("description", ""),
            "display_order": cat_data.get("display_order", 0),
            "is_active": True,
            "routes_to_kitchen": cat_data.get("routes_to_kitchen", True),
        }
        if dry_run:
            category = None
            summary["categories_created"] += 1
        else:
            category, created = MenuCategory.objects.get_or_create(
                name=cat_data["name"],
                defaults=cat_defaults,
            )
            if not created:
                for key, val in cat_defaults.items():
                    setattr(category, key, val)
                category.save()
            else:
                summary["categories_created"] += 1

        dg_name = cat_data.get("display_group")
        display_group = display_group_by_name.get(dg_name) if dg_name else None

        for item_data in cat_data.get("items", []):
            display_order_item += 1
            item_name = item_data["item_name"]
            unit_price = Decimal(str(item_data["unit_price"]))
            item_type = item_data.get("type", InventoryType.Service.value)
            desc = _full_description(item_data)

            if dry_run:
                summary["items_created"] += 1
                summary["menu_items_created"] += 1
                continue

            item, item_created = Item.objects.get_or_create(
                item_name=item_name,
                defaults={
                    "type": item_type,
                    "unit_price": unit_price,
                    "description": desc,
                    "item_category_id": ic_data["code"],
                    "unit_of_measure": uom,
                },
            )
            if item_created:
                summary["items_created"] += 1
            else:
                changed = False
                if item.unit_price != unit_price:
                    item.unit_price = unit_price
                    changed = True
                if (item.description or "") != desc:
                    item.description = desc
                    changed = True
                if item.type != item_type:
                    item.type = item_type
                    changed = True
                if changed:
                    item.save()
                    summary["items_updated"] += 1
                else:
                    summary["skipped"] += 1

            ItemUnitOfMeasure.objects.get_or_create(
                item=item,
                unit_of_measure=uom,
                defaults={
                    "quantity_per_unit": 1,
                    "default": True,
                    "price": unit_price,
                },
            )

            routes = item_data.get("routes_to_kitchen")
            if routes is None:
                routes = cat_data.get("routes_to_kitchen", True)

            mi_defaults = {
                "category": category,
                "menu": menu,
                "display_group": display_group,
                "description": desc,
                "is_available": True,
                "routes_to_kitchen": routes,
                "dietary_info": item_data.get("dietary_info", ["halal"]),
                "is_featured": item_data.get("is_featured", False),
                "preparation_time": item_data.get("preparation_time", 15),
                "display_order": display_order_item,
            }
            menu_item, mi_created = MenuItem.objects.get_or_create(
                item=item,
                defaults=mi_defaults,
            )
            if mi_created:
                summary["menu_items_created"] += 1
            else:
                mi_changed = False
                for key, val in mi_defaults.items():
                    if getattr(menu_item, key) != val:
                        setattr(menu_item, key, val)
                        mi_changed = True
                if mi_changed:
                    menu_item.save()
                    summary["menu_items_updated"] += 1

    return summary


class Command(BaseCommand):
    help = (
        "Seed Royal Joint Restaurant menu items (POS Items + MenuCategories + MenuItems). "
        "Discoverable by Seed Manager."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant",
            "--schema",
            dest="tenant",
            type=str,
            help="Tenant schema name (use with tenant_command).",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Remove existing Royal Joint menu rows before seeding.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Count records that would be created without writing to the database.",
        )
        parser.add_argument(
            "--export-json",
            action="store_true",
            help="Write data/restaurant/royal_joint_menu.json from the Python catalog.",
        )

    def handle(self, *args, **options):
        if options.get("export_json"):
            self._export_json()
            return

        tenant = options.get("tenant")
        dry_run = options.get("dry_run", False)
        clear = options.get("clear", False)

        def run():
            summary = seed_royal_joint_menu(clear=clear, dry_run=dry_run)
            prefix = "[DRY RUN] " if dry_run else ""
            self.stdout.write(
                self.style.SUCCESS(
                    f"{prefix}Royal Joint menu seed complete: "
                    f"{summary['items_created']} items created, "
                    f"{summary['items_updated']} items updated, "
                    f"{summary['menu_items_created']} menu items created, "
                    f"{summary['menu_items_updated']} menu items updated, "
                    f"{summary['categories_created']} categories, "
                    f"{summary['display_groups_created']} display groups."
                )
            )

        if tenant:
            with schema_context(tenant):
                run()
        else:
            run()

    def _export_json(self):
        out_path = (
            Path(__file__).resolve().parents[3]
            / "data"
            / "restaurant"
            / "royal_joint_menu.json"
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        catalog = build_catalog()
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(catalog, f, indent=2, ensure_ascii=False)
        self.stdout.write(self.style.SUCCESS(f"Exported {out_path}"))
