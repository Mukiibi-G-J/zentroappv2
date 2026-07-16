"""
Align page_engine PageId with ObjectId using the Zentro page registry.

After this runs, registered pages satisfy::

    page_id == object_id == ZENTRO_PAGE_REGISTRY[name]

New IDs live in 10000+ so they do not collide with old sequential page_ids.

Usage::

    python manage.py tenant_command align_zentro_page_ids --schema=primewise
    python manage.py tenant_command setup_page_permissions --schema=primewise
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import connection, transaction

from pages.bc_page_ids import ZENTRO_PAGE_REGISTRY
from pages.models import Page
from pages.permission_sync import sync_all_page_permission_objects


# (table, column) FKs that reference page_engine_page.page_id within the tenant schema
_PAGE_FK_COLUMNS = (
    ('page_engine_action', 'page_id'),
    ('page_engine_control', 'page_id'),
    ('page_engine_control', 'drill_down_page_id'),
    ('page_engine_control', 'part_page_id'),
    ('page_engine_field', 'page_id'),
    ('page_engine_field', 'drill_down_page_id'),
    ('page_engine_field', 'lookup_page_id'),
    ('page_engine_page', 'card_page_id'),
    ('page_engine_page', 'header_page_id'),
    ('authentication_applicationprofile', 'role_centre_page_id'),
)


def _fk_constraint_names(cursor, schema: str) -> list[tuple[str, str]]:
    """Return [(table, constraint_name), ...] for page_id FKs we touch."""
    found: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for table, col in _PAGE_FK_COLUMNS:
        cursor.execute(
            """
            SELECT con.conname
            FROM pg_constraint con
            JOIN pg_class c ON c.oid = con.conrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_attribute a
              ON a.attrelid = c.oid AND a.attnum = ANY (con.conkey)
            WHERE con.contype = 'f'
              AND n.nspname = %s
              AND c.relname = %s
              AND a.attname = %s
            """,
            [schema, table, col],
        )
        for (conname,) in cursor.fetchall():
            key = (table, conname)
            if key not in seen:
                seen.add(key)
                found.append(key)
    return found


def align_zentro_page_ids(*, sync_permissions: bool = True) -> dict:
    """
    Remap page PKs so PageId == ObjectId from ZENTRO_PAGE_REGISTRY.

    Returns ``{'mapped': n, 'skipped_missing': n, 'already_aligned': bool}``.
    """
    schema = connection.schema_name
    mapping: dict[int, int] = {}
    skipped = 0

    for name, (new_id, _module) in ZENTRO_PAGE_REGISTRY.items():
        page = Page.objects.filter(name=name).first()
        if page is None:
            skipped += 1
            continue
        if page.page_id == new_id:
            if page.object_id != new_id:
                Page.objects.filter(pk=page.pk).update(object_id=new_id)
            continue
        if Page.objects.filter(pk=new_id).exclude(name=name).exists():
            raise RuntimeError(
                f'Cannot map {name}: target page_id={new_id} already used by another page'
            )
        mapping[page.page_id] = new_id

    with transaction.atomic():
        with connection.cursor() as cursor:
            fk_constraints = _fk_constraint_names(cursor, schema)
            for table, conname in fk_constraints:
                cursor.execute(
                    f'ALTER TABLE {schema}.{table} '
                    f'ALTER CONSTRAINT {conname} DEFERRABLE INITIALLY DEFERRED'
                )
            cursor.execute('SET CONSTRAINTS ALL DEFERRED')

            if mapping:
                # Free unique object_id slots before PK moves
                Page.objects.filter(page_id__in=mapping.keys()).update(object_id=None)

                for old_id, new_id in sorted(mapping.items(), key=lambda x: -x[1]):
                    for table, col in _PAGE_FK_COLUMNS:
                        cursor.execute(
                            f'UPDATE {schema}.{table} '
                            f'SET {col} = %s WHERE {col} = %s',
                            [new_id, old_id],
                        )
                    cursor.execute(
                        f'UPDATE {schema}.page_engine_page '
                        f'SET page_id = %s, object_id = %s WHERE page_id = %s',
                        [new_id, new_id, old_id],
                    )

                cursor.execute(
                    f"""
                    SELECT setval(
                        pg_get_serial_sequence(%s, 'page_id'),
                        GREATEST(
                            (SELECT COALESCE(MAX(page_id), 1)
                             FROM {schema}.page_engine_page),
                            1
                        )
                    )
                    """,
                    [f'{schema}.page_engine_page'],
                )

            for name, (new_id, _) in ZENTRO_PAGE_REGISTRY.items():
                Page.objects.filter(name=name).exclude(object_id=new_id).update(
                    object_id=new_id
                )

        if sync_permissions:
            sync_all_page_permission_objects()

    return {
        'mapped': len(mapping),
        'skipped_missing': skipped,
        'already_aligned': not mapping,
    }


class Command(BaseCommand):
    help = 'Set PageId = ObjectId from ZENTRO_PAGE_REGISTRY (10xxx bands)'

    def handle(self, *args, **options):
        stats = align_zentro_page_ids()
        if stats['already_aligned']:
            self.stdout.write(
                self.style.SUCCESS('PageIds already aligned; object_ids synced')
            )
            return
        self.stdout.write(
            self.style.SUCCESS(
                f"Aligned {stats['mapped']} page PKs to Zentro IDs "
                f"(skipped missing names={stats['skipped_missing']})"
            )
        )
