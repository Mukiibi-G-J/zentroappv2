from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0012_users_card_user_setup_branch_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='page',
            name='object_id',
            field=models.IntegerField(
                blank=True,
                db_index=True,
                help_text=(
                    'BC-style permission object ID (e.g. 1016 = BC page 16). '
                    'Stable across tenants; synced to base.Objects for permission sets.'
                ),
                null=True,
                unique=True,
            ),
        ),
    ]
