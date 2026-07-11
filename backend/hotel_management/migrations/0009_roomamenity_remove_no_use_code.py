# Revert RoomAmenity to code-only (lookup data). Remove no column if present.

from django.db import migrations


def apply(apps, schema_editor):
    from django.db import connection

    with connection.cursor() as cursor:
        # 1. Drop no column if it exists
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = current_schema()
            AND table_name = 'hotel_management_roomamenity'
            AND column_name = 'no';
        """)
        if cursor.fetchone() is not None:
            cursor.execute("""
                ALTER TABLE hotel_management_roomamenity
                DROP CONSTRAINT IF EXISTS hotel_management_roomamenity_no_key;
            """)
            cursor.execute("""
                ALTER TABLE hotel_management_roomamenity DROP COLUMN IF EXISTS no;
            """)

        # 2. Restore code: NOT NULL and UNIQUE if missing
        cursor.execute("""
            SELECT 1 FROM pg_constraint c
            JOIN pg_class t ON c.conrelid = t.oid
            WHERE t.relname = 'hotel_management_roomamenity'
            AND c.conname = 'hotel_management_roomamenity_code_key';
        """)
        if cursor.fetchone() is None:
            cursor.execute("""
                ALTER TABLE hotel_management_roomamenity
                ADD CONSTRAINT hotel_management_roomamenity_code_key UNIQUE (code);
            """)

        # Backfill empty code before NOT NULL (if 0008 made it nullable)
        cursor.execute("""
            UPDATE hotel_management_roomamenity
            SET code = 'AM-' || id::text
            WHERE code IS NULL OR TRIM(code) = '';
        """)
        cursor.execute("""
            ALTER TABLE hotel_management_roomamenity
            ALTER COLUMN code SET NOT NULL;
        """)


def reverse(apps, schema_editor):
    # Reversing would re-apply 0008 logic; leave as no-op
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("hotel_management", "0008_roomamenity_no_series"),
    ]

    operations = [
        migrations.RunPython(apply, reverse),
    ]
