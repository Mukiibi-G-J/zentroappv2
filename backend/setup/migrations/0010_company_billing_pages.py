import uuid

from django.db import migrations, models
import utils.utils


class Migration(migrations.Migration):

    dependencies = [
        ('setup', '0009_companyinformation'),
    ]

    operations = [
        migrations.CreateModel(
            name='CompanySubscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('system_id', utils.utils.UUIField(db_index=True, default=uuid.uuid4, editable=False, max_length=36, unique=True, verbose_name='System ID')),
                ('plan', models.CharField(blank=True, default='', max_length=50)),
                ('status', models.CharField(blank=True, default='', max_length=20)),
                ('billing_cycle', models.CharField(blank=True, default='', max_length=20)),
                ('is_active', models.BooleanField(default=False)),
                ('in_grace_period', models.BooleanField(default=False)),
                ('is_paid', models.BooleanField(default=False)),
                ('days_remaining', models.IntegerField(default=0)),
                ('grace_days_remaining', models.IntegerField(default=0)),
                ('period_end_date', models.DateField(blank=True, null=True)),
                ('payment_due_date', models.DateField(blank=True, null=True)),
                ('subscription_end_date', models.DateField(blank=True, null=True)),
                ('access_lock_date', models.DateField(blank=True, null=True)),
            ],
            options={
                'verbose_name': 'Company Subscription',
                'verbose_name_plural': 'Company Subscription',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='CompanyBillingHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('system_id', utils.utils.UUIField(db_index=True, default=uuid.uuid4, editable=False, max_length=36, unique=True, verbose_name='System ID')),
                ('public_id', models.IntegerField(db_index=True, unique=True)),
                ('reference_number', models.CharField(max_length=10)),
                ('product', models.CharField(max_length=100)),
                ('status', models.CharField(max_length=30)),
                ('billing_date', models.DateField()),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('currency', models.CharField(default='UGX', max_length=3)),
            ],
            options={
                'verbose_name': 'Billing History',
                'verbose_name_plural': 'Billing History',
                'ordering': ['-billing_date', '-id'],
            },
        ),
        migrations.CreateModel(
            name='CompanyPaymentMethod',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('system_id', utils.utils.UUIField(db_index=True, default=uuid.uuid4, editable=False, max_length=36, unique=True, verbose_name='System ID')),
                ('public_id', models.IntegerField(db_index=True, unique=True)),
                ('method_type', models.CharField(max_length=50)),
                ('holder_name', models.CharField(max_length=100)),
                ('last_four_digits', models.CharField(blank=True, default='', max_length=4)),
                ('is_primary', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name': 'Payment Method',
                'verbose_name_plural': 'Payment Methods',
                'ordering': ['-is_primary', 'holder_name'],
            },
        ),
    ]
