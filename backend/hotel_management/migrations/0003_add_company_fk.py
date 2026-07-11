# No-op - company FK was added by mistake; 0004 removes it (django-tenants handles isolation)

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('hotel_management', '0002_allow_empty_description'),
    ]

    operations = []  # No-op placeholder for migration history compatibility
