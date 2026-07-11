"""
Rename a BRANCH (Global Dimension 1) DimensionValue code and keep Location.code in sync.

Why this exists:
- The frontend shows branch names from DimensionValue.code/description (GET /api/sales/setup/).
- Multiple backend flows assume the "Zentro convention": Location.code == branch DimensionValue.code.
  If you rename the DimensionValue.code without updating Location.code, inventory/POS flows can break.

Safe characteristics:
- FK relationships are by DimensionValue.id, so updating the *code* is generally safe.
- This command validates uniqueness collisions before mutating anything.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.utils import DatabaseError, ProgrammingError
from django.apps import apps

try:
    from django_tenants.utils import get_public_schema_name, get_tenant_model, schema_context
except ImportError:  # pragma: no cover
    schema_context = None
    get_tenant_model = None

    def get_public_schema_name():  # type: ignore
        return "public"


@dataclass(frozen=True)
class _RenamePlan:
    old_code: str
    new_code: str
    update_dimension_description: bool
    update_location_description: bool
    dry_run: bool


class Command(BaseCommand):
    help = "Rename a branch DimensionValue.code and matching Location.code (multi-tenant aware)."

    def add_arguments(self, parser):
        parser.add_argument("old_code", type=str, help="Existing branch code, e.g. Kabale")
        parser.add_argument("new_code", type=str, help="New branch code, e.g. CENTRAL")
        parser.add_argument(
            "--schema",
            type=str,
            help="Single tenant schema; if omitted, applies to all non-public tenant schemas.",
        )
        parser.add_argument(
            "--no-update-dimension-description",
            action="store_true",
            help="Do not change DimensionValue.description (default is to set it to new_code when it exactly matches old_code).",
        )
        parser.add_argument(
            "--update-location-description",
            action="store_true",
            help="Also update items.Location.description when it exactly matches old_code (default: off).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would change, but do not write anything.",
        )

    def handle(self, *args, **options):
        old_code = (options["old_code"] or "").strip()
        new_code = (options["new_code"] or "").strip()
        if not old_code or not new_code:
            raise CommandError("Both old_code and new_code are required.")
        if old_code.lower() == new_code.lower():
            raise CommandError("old_code and new_code are the same (case-insensitive). Nothing to do.")

        plan = _RenamePlan(
            old_code=old_code,
            new_code=new_code,
            update_dimension_description=not bool(options.get("no_update_dimension_description")),
            update_location_description=bool(options.get("update_location_description")),
            dry_run=bool(options.get("dry_run")),
        )

        schema_arg = (options.get("schema") or "").strip() or None
        schemas = self._schemas(schema_arg)

        changed_any = False
        for schema in schemas:
            if schema_context:
                with schema_context(schema):
                    changed_any = self._apply_one(schema, plan) or changed_any
            else:
                self._set_path(schema)
                try:
                    changed_any = self._apply_one(schema, plan) or changed_any
                finally:
                    self._set_path(get_public_schema_name())

        if not changed_any:
            self.stdout.write(self.style.WARNING("No changes were applied (no matching rows found)."))

    def _schemas(self, one: str | None):
        if one:
            return [one]
        if not get_tenant_model:
            # Non-tenanted install: operate on current schema (often public).
            return [get_public_schema_name()]
        Company = get_tenant_model()
        return list(
            Company.objects.exclude(schema_name=get_public_schema_name())
            .values_list("schema_name", flat=True)
            .order_by("schema_name")
        )

    def _set_path(self, schema: str):
        with connection.cursor() as c:
            c.execute("SET search_path TO %s, public", [schema])

    def _apply_one(self, schema: str, plan: _RenamePlan) -> bool:
        from dimension.models import Dimension, DimensionValue
        from items.models import Location

        # Only target the tenant's branch dimension value.
        try:
            branch_dim = Dimension.objects.filter(code__iexact="BRANCH").first()
        except (ProgrammingError, DatabaseError) as e:
            self.stdout.write(
                self.style.WARNING(
                    f"{schema}: schema drift while reading Dimension/DimensionValue tables: {e!s}"[:300]
                )
            )
            return False
        if not branch_dim:
            self.stdout.write(self.style.WARNING(f"{schema}: BRANCH Dimension not found; skipping."))
            return False

        try:
            dv = (
                DimensionValue.objects.filter(
                    dimension_code_id=branch_dim.id, code__iexact=plan.old_code
                )
                .order_by("id")
                .first()
            )
        except (ProgrammingError, DatabaseError) as e:
            self.stdout.write(
                self.style.WARNING(
                    f"{schema}: schema drift while reading DimensionValue rows: {e!s}"[:300]
                )
            )
            return False
        if not dv:
            self.stdout.write(self.style.WARNING(f"{schema}: DimensionValue {plan.old_code!r} not found; skipping."))
            return False

        # Collision checks (DimensionValue.code is globally unique in this schema).
        try:
            dv_collision = (
                DimensionValue.objects.filter(code__iexact=plan.new_code)
                .exclude(id=dv.id)
                .first()
            )
        except (ProgrammingError, DatabaseError) as e:
            self.stdout.write(
                self.style.WARNING(
                    f"{schema}: schema drift while checking DimensionValue collisions: {e!s}"[:300]
                )
            )
            return False
        if dv_collision:
            raise CommandError(
                f"{schema}: cannot rename DimensionValue {plan.old_code!r} -> {plan.new_code!r}: "
                f"DimensionValue with code {dv_collision.code!r} already exists (id={dv_collision.id})."
            )

        # Location sync: keep Location.code == branch code.
        try:
            loc = Location.objects.filter(code__iexact=plan.old_code).order_by("id").first()
            loc_target = Location.objects.filter(code__iexact=plan.new_code).order_by("id").first()
        except (ProgrammingError, DatabaseError) as e:
            self.stdout.write(
                self.style.WARNING(
                    f"{schema}: schema drift while reading Location rows: {e!s}"[:300]
                )
            )
            return False

        dim_desc_will_change = False
        new_dim_desc = dv.description
        if plan.update_dimension_description and (dv.description or "").strip().lower() == plan.old_code.strip().lower():
            new_dim_desc = plan.new_code
            dim_desc_will_change = True

        loc_desc_will_change = False
        new_loc_desc = loc.description if loc else None
        if (
            loc
            and plan.update_location_description
            and (loc.description or "").strip().lower() == plan.old_code.strip().lower()
        ):
            new_loc_desc = plan.new_code
            loc_desc_will_change = True

        # Show plan.
        self.stdout.write(
            f"{schema}: DimensionValue(id={dv.id}) {dv.code!r} -> {plan.new_code!r}"
            + (f" (description {dv.description!r} -> {new_dim_desc!r})" if dim_desc_will_change else "")
        )
        if loc:
            self.stdout.write(
                f"{schema}: Location(id={loc.id}) {loc.code!r} -> {plan.new_code!r} (will migrate FK refs; no in-place PK update)"
                + (
                    f" (description {loc.description!r} -> {new_loc_desc!r})"
                    if loc_desc_will_change
                    else ""
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"{schema}: Location with code {plan.old_code!r} not found. "
                    "This can break inventory/POS flows unless you create/rename a matching Location."
                )
            )
        if loc_target and loc and loc_target.id != loc.id:
            self.stdout.write(
                self.style.WARNING(
                    f"{schema}: Location with code {plan.new_code!r} already exists (id={loc_target.id}). "
                    "Will move foreign keys to it and delete the old one if safe."
                )
            )

        if plan.dry_run:
            return False

        with transaction.atomic():
            dv.code = plan.new_code
            if dim_desc_will_change:
                dv.description = new_dim_desc
            dv.save(update_fields=["code", "description"] if dim_desc_will_change else ["code"])

            if loc:
                # IMPORTANT:
                # Many models reference Location via to_field="code", so Location.code becomes the FK target.
                # Postgres will reject updating Location.code if any FK lacks ON UPDATE CASCADE.
                # So we create/ensure the target Location row exists, then update all FK columns to point
                # at the new code, then delete the old Location row.

                if not loc_target:
                    loc_target = Location.objects.create(
                        code=plan.new_code,
                        description=(new_loc_desc if (loc_desc_will_change and new_loc_desc is not None) else loc.description),
                        address=loc.address,
                        city=loc.city,
                        phone=loc.phone,
                        email=loc.email,
                    )
                elif loc_desc_will_change and new_loc_desc is not None:
                    # Only update description on the target when explicitly requested by flags.
                    loc_target.description = new_loc_desc
                    loc_target.save(update_fields=["description"])

                updated = 0
                existing_tables = set(connection.introspection.table_names())
                for model in apps.get_models():
                    if not getattr(model._meta, "managed", False) or model._meta.proxy:
                        continue
                    # Skip models whose tables don't exist in this tenant schema (schema drift).
                    if model._meta.db_table not in existing_tables:
                        continue
                    for field in model._meta.fields:
                        if not getattr(field, "is_relation", False) or not getattr(field, "many_to_one", False):
                            continue
                        remote = getattr(field, "remote_field", None)
                        if not remote or remote.model is None:
                            continue
                        try:
                            if remote.model is Location:
                                attname = field.attname
                                # If FK is to_field="code", the stored value is the code string.
                                if getattr(remote, "field_name", None) == "code":
                                    try:
                                        n = model.objects.filter(**{attname: loc.code}).update(
                                            **{attname: loc_target.code}
                                        )
                                    except Exception:
                                        continue
                                    updated += int(n or 0)
                                else:
                                    # Normal FK to Location.id (integer).
                                    try:
                                        n = model.objects.filter(**{attname: loc.pk}).update(
                                            **{attname: loc_target.pk}
                                        )
                                    except Exception:
                                        continue
                                    updated += int(n or 0)
                        except Exception:
                            continue

                # Finally remove the old location row (now that FKs point elsewhere).
                # Avoid ORM .delete() here: Django's cascade collector queries *all* related models,
                # which can crash on tenant schemas missing some tables (schema drift).
                # We rely on the database's FK constraints instead.
                with connection.cursor() as c:
                    c.execute(
                        "DELETE FROM items_location WHERE code = %s",
                        [loc.code],
                    )
                self.stdout.write(self.style.SUCCESS(f"{schema}: moved {updated} FK reference(s) from Location {plan.old_code!r} -> {plan.new_code!r}"))

        return True

