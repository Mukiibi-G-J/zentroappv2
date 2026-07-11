# State-only migration: 0022 already renamed dimension_1_id -> global_dimension_1_id in the DB.
# This migration only updates Django's migration state so it matches the current models.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('items', '0022_rename_dimension_1_to_global_dimension_1'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RenameField(
                    model_name='itemledgerentries',
                    old_name='dimension_1',
                    new_name='global_dimension_1',
                ),
                migrations.RenameField(
                    model_name='valueentry',
                    old_name='dimension_1',
                    new_name='global_dimension_1',
                ),
            ],
            database_operations=[],  # 0022 already did the column rename
        ),
    ]
