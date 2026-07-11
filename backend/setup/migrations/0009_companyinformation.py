import uuid

from django.db import migrations, models
import utils.utils


class Migration(migrations.Migration):

    dependencies = [
        ('setup', '0008_add_show_adjustment_history_before_after'),
    ]

    operations = [
        migrations.CreateModel(
            name='CompanyInformation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('system_id', utils.utils.UUIField(db_index=True, default=uuid.uuid4, editable=False, max_length=36, unique=True, verbose_name='System ID')),
                ('name', models.CharField(help_text='Legal company name (read-only)', max_length=100, verbose_name='Company Name')),
                ('display_name', models.CharField(blank=True, max_length=100, verbose_name='Display Name')),
                ('logo', models.ImageField(blank=True, null=True, upload_to='company_logos/')),
                ('address', models.CharField(blank=True, default='', max_length=255)),
                ('phone', models.CharField(blank=True, default='', max_length=255)),
                ('email', models.EmailField(blank=True, default='', max_length=254)),
                ('website', models.URLField(blank=True, max_length=255, null=True)),
                ('city', models.CharField(blank=True, max_length=100, null=True)),
                ('country', models.CharField(blank=True, max_length=100, null=True)),
                ('tin', models.CharField(blank=True, default='', max_length=20)),
            ],
            options={
                'verbose_name': 'Company Information',
                'verbose_name_plural': 'Company Information',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['created_at'], name='setup_compa_created_idx'),
                    models.Index(fields=['system_id'], name='setup_compa_system_idx'),
                ],
            },
        ),
    ]
