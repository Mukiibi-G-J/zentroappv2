"""
If 0007 was not applied on a schema (or failed partway), the ORM expects
restaurant_management_menu / menu_id while the DB may still have
restaurant_management_servicemenu / service_menu_id. Normalize physical names.
Safe no-op when already aligned.
"""

from django.db import migrations


def _table_exists(cursor, table: str) -> bool:
    cursor.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = current_schema()
              AND table_name = %s
        );
        """,
        [table],
    )
    return bool(cursor.fetchone()[0])


def _column_exists(cursor, table: str, column: str) -> bool:
    cursor.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = %s
              AND column_name = %s
        );
        """,
        [table, column],
    )
    return bool(cursor.fetchone()[0])


def forwards(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        if _table_exists(cursor, "restaurant_management_servicemenu") and not _table_exists(
            cursor, "restaurant_management_menu"
        ):
            cursor.execute(
                'ALTER TABLE "restaurant_management_servicemenu" '
                'RENAME TO "restaurant_management_menu"'
            )
        if _table_exists(cursor, "restaurant_management_servicemenulocation") and not _table_exists(
            cursor, "restaurant_management_menulocation"
        ):
            cursor.execute(
                'ALTER TABLE "restaurant_management_servicemenulocation" '
                'RENAME TO "restaurant_management_menulocation"'
            )
        if _column_exists(
            cursor, "restaurant_management_menuitem", "service_menu_id"
        ) and not _column_exists(cursor, "restaurant_management_menuitem", "menu_id"):
            cursor.execute(
                'ALTER TABLE "restaurant_management_menuitem" '
                'RENAME COLUMN "service_menu_id" TO "menu_id"'
            )


def backwards_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("restaurant_management", "0007_rename_servicemenu_to_menu"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards_noop),
    ]
