# Drop company_id from RoomAmenity - django-tenants uses schema isolation, not company_id

from django.db import migrations


def apply(apps, schema_editor):
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = current_schema()
            AND table_name = 'hotel_management_roomamenity'
            AND column_name = 'company_id';
        """)
        if cursor.fetchone() is not None:
            cursor.execute("""
                ALTER TABLE hotel_management_roomamenity
                DROP COLUMN IF EXISTS company_id;
            """)


def reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("hotel_management", "0009_roomamenity_remove_no_use_code"),
    ]

    operations = [
        migrations.RunPython(apply, reverse),
    ]
