import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Replace UserPersonalization.role CharField with FK to ApplicationProfile, also named role.
    If 0022 already renamed application_profile -> role_profile, run 0023 instead.
    """

    dependencies = [
        ('authentication', '0021_applicationprofile'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='userpersonalization',
            name='role',
        ),
        migrations.RenameField(
            model_name='userpersonalization',
            old_name='application_profile',
            new_name='role',
        ),
        migrations.AlterField(
            model_name='userpersonalization',
            name='role',
            field=models.ForeignKey(
                blank=True,
                help_text='Role Centre profile chosen by the user (User Settings)',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='user_personalizations',
                to='authentication.applicationprofile',
            ),
        ),
    ]
