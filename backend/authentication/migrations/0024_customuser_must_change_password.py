from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0023_ensure_customuser_system_id_column'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='must_change_password',
            field=models.BooleanField(
                default=False,
                help_text='When enabled, the user must set a new password at next login.',
            ),
        ),
    ]
