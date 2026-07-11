# RoomAmenity NoSeries - idempotent migration for multi-tenant

from django.db import migrations


def apply_no_series(apps, schema_editor):
    """Add no column and unique constraint. Idempotent for partial-fail recovery."""
    from django.db import connection

    with connection.cursor() as cursor:
        # 1. Add no column if missing
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = current_schema()
            AND table_name = 'hotel_management_roomamenity'
            AND column_name = 'no';
        """)
        if cursor.fetchone() is None:
            cursor.execute("""
                ALTER TABLE hotel_management_roomamenity
                ADD COLUMN no VARCHAR(50) NOT NULL DEFAULT '';
            """)
            cursor.execute("ALTER TABLE hotel_management_roomamenity ALTER COLUMN no DROP DEFAULT;")

        # 2. Drop unique constraint on code (we're making it optional)
        cursor.execute("""
            ALTER TABLE hotel_management_roomamenity
            DROP CONSTRAINT IF EXISTS hotel_management_roomamenity_code_key;
        """)
        # 3. Make code allow blank
        cursor.execute("""
            ALTER TABLE hotel_management_roomamenity
            ALTER COLUMN code DROP NOT NULL,
            ALTER COLUMN code SET DEFAULT '';
        """)

        # 4. Backfill no for rows where no is empty
        cursor.execute("""
            UPDATE hotel_management_roomamenity
            SET no = COALESCE(NULLIF(TRIM(code), ''), 'AM-' || id::text)
            WHERE no = '' OR no IS NULL;
        """)

        # 5. Add unique constraint if missing
        cursor.execute("""
            SELECT 1 FROM pg_constraint c
            JOIN pg_class t ON c.conrelid = t.oid
            WHERE t.relname = 'hotel_management_roomamenity'
            AND c.conname = 'hotel_management_roomamenity_no_key';
        """)
        if cursor.fetchone() is None:
            cursor.execute("""
                ALTER TABLE hotel_management_roomamenity
                ADD CONSTRAINT hotel_management_roomamenity_no_key UNIQUE (no);
            """)



def reverse_migration(apps, schema_editor):
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("""
            ALTER TABLE hotel_management_roomamenity
            DROP CONSTRAINT IF EXISTS hotel_management_roomamenity_no_key;
        """)
        cursor.execute("""
            ALTER TABLE hotel_management_roomamenity DROP COLUMN IF EXISTS no;
        """)


class Migration(migrations.Migration):

    dependencies = [
        ("hotel_management", "0007_room_notes_default"),
    ]

    operations = [
        migrations.RunPython(apply_no_series, reverse_migration),
    ]
