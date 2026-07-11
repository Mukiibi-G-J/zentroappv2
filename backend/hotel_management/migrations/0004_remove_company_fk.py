# Remove company FK - using django-tenants for isolation, company_id not needed

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('hotel_management', '0003_add_company_fk'),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE hotel_management_roomtype DROP COLUMN IF EXISTS company_id;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="ALTER TABLE hotel_management_room DROP COLUMN IF EXISTS company_id;",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
