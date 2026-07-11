"""Safely rename items.Location.code when FKs use to_field='code' (no ON UPDATE CASCADE)."""

from __future__ import annotations

from django.apps import apps
from django.db import connection, transaction

from items.models import Location


def rename_location_code(
    old_code: str,
    new_code: str,
    *,
    description: str | None = None,
    address: str | None = None,
    city: str | None = None,
    phone: str | None = None,
    email: str | None = None,
) -> Location:
    """
    Repoint FKs that reference Location.code, then set the code on the same row (keeps pk).

    If ``new_code`` already belongs to another Location row, FKs are moved to that row
    and the old row is removed (same strategy as rename_branch_dimension_value).
    """
    old_code = (old_code or "").strip()
    new_code = (new_code or "").strip()
    if not old_code or not new_code:
        raise ValueError("Location code cannot be empty.")

    loc = Location.objects.filter(code=old_code).first()
    if not loc:
        raise ValueError(f"Location with code {old_code!r} not found.")

    if old_code == new_code:
        _apply_scalar_updates(loc, description, address, city, phone, email)
        loc.save()
        return loc

    other = Location.objects.filter(code=new_code).exclude(pk=loc.pk).first()
    if other:
        return _merge_into_existing_location(
            loc, other, description, address, city, phone, email
        )

    with transaction.atomic():
        _repoint_location_foreign_keys(old_code, new_code)
        loc.code = new_code
        _apply_scalar_updates(loc, description, address, city, phone, email)
        loc.save()
    return loc


def _merge_into_existing_location(
    loc: Location,
    loc_target: Location,
    description: str | None,
    address: str | None,
    city: str | None,
    phone: str | None,
    email: str | None,
) -> Location:
    with transaction.atomic():
        _repoint_location_foreign_keys(loc.code, loc_target.code)
        _repoint_location_id_foreign_keys(loc.pk, loc_target.pk)
        _apply_scalar_updates(
            loc_target, description, address, city, phone, email
        )
        loc_target.save()
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM items_location WHERE code = %s",
                [loc.code],
            )
    return loc_target


def _apply_scalar_updates(
    loc: Location,
    description: str | None,
    address: str | None,
    city: str | None,
    phone: str | None,
    email: str | None,
) -> None:
    if description is not None:
        loc.description = description
    if address is not None:
        loc.address = address
    if city is not None:
        loc.city = city
    if phone is not None:
        loc.phone = phone
    if email is not None:
        loc.email = email


def _repoint_location_foreign_keys(old_code: str, new_code: str) -> int:
    updated = 0
    existing_tables = set(connection.introspection.table_names())
    for model in apps.get_models():
        if not getattr(model._meta, "managed", False) or model._meta.proxy:
            continue
        if model._meta.db_table not in existing_tables:
            continue
        for field in model._meta.fields:
            if not getattr(field, "is_relation", False) or not getattr(
                field, "many_to_one", False
            ):
                continue
            remote = getattr(field, "remote_field", None)
            if not remote or remote.model is not Location:
                continue
            if getattr(remote, "field_name", None) != "code":
                continue
            attname = field.attname
            try:
                n = model.objects.filter(**{attname: old_code}).update(
                    **{attname: new_code}
                )
                updated += int(n or 0)
            except Exception:
                continue
    return updated


def _repoint_location_id_foreign_keys(old_pk: int, new_pk: int) -> int:
    if old_pk == new_pk:
        return 0
    updated = 0
    existing_tables = set(connection.introspection.table_names())
    for model in apps.get_models():
        if not getattr(model._meta, "managed", False) or model._meta.proxy:
            continue
        if model._meta.db_table not in existing_tables:
            continue
        for field in model._meta.fields:
            if not getattr(field, "is_relation", False) or not getattr(
                field, "many_to_one", False
            ):
                continue
            remote = getattr(field, "remote_field", None)
            if not remote or remote.model is not Location:
                continue
            if getattr(remote, "field_name", None) == "code":
                continue
            attname = field.attname
            try:
                n = model.objects.filter(**{attname: old_pk}).update(
                    **{attname: new_pk}
                )
                updated += int(n or 0)
            except Exception:
                continue
    return updated
