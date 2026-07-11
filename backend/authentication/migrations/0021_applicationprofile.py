# Generated manually for Role Centre profile chain

import django.db.models.deletion
import utils.utils
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0020_userpersonalization'),
        ('pages', '0004_tablerelation'),
    ]

    operations = [
        migrations.CreateModel(
            name='ApplicationProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('system_id', utils.utils.UUIField(db_index=True, default=uuid.uuid4, editable=False, max_length=36, unique=True, verbose_name='System ID')),
                ('code', models.CharField(help_text='Profile ID, e.g. SALES-MGR', max_length=50, unique=True)),
                ('description', models.CharField(max_length=200)),
                ('role_centre_page', models.ForeignKey(help_text='Role Centre page shown when this profile is active', on_delete=django.db.models.deletion.PROTECT, related_name='application_profiles', to='pages.page')),
            ],
            options={
                'verbose_name': 'Application Profile',
                'verbose_name_plural': 'Application Profiles',
                'db_table': 'authentication_applicationprofile',
                'ordering': ['code'],
            },
        ),
        migrations.AddField(
            model_name='userpersonalization',
            name='application_profile',
            field=models.ForeignKey(blank=True, help_text='Role Centre profile chosen by the user (User Settings)', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='user_personalizations', to='authentication.applicationprofile'),
        ),
    ]
