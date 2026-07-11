import django.db.models.deletion
import purchases.models
import utils.utils
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0001_initial'),
        ('financials', '0002_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PaymentLine',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('system_id', utils.utils.UUIField(db_index=True, default=uuid.uuid4, editable=False, max_length=36, unique=True, verbose_name='System ID')),
                ('line_no', models.IntegerField(default=10000, verbose_name='Line No.')),
                ('account_type', models.CharField(blank=True, choices=[('Customer', 'Customer'), ('Vendor', 'Vendor'), ('G/L Account', 'G/L Account')], max_length=20, null=True, verbose_name='Account Type')),
                ('account_no', models.CharField(blank=True, max_length=50, null=True, verbose_name='Account No.')),
                ('description', models.TextField(blank=True, null=True, verbose_name='Description')),
                ('amount', models.IntegerField(blank=True, null=True, verbose_name='Amount')),
                ('payment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lines', to='payments.paymentjournal', verbose_name='Payment')),
                ('payment_method', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='payment_lines', to='financials.paymentmethod', verbose_name='Payment Method')),
            ],
            options={
                'verbose_name': 'Payment Line',
                'verbose_name_plural': 'Payment Lines',
                'ordering': ['payment', 'line_no'],
            },
        ),
        migrations.AddIndex(
            model_name='paymentline',
            index=models.Index(fields=['payment', 'line_no'], name='pay_line_idx'),
        ),
        migrations.CreateModel(
            name='CashReceiptJournalBatch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('system_id', utils.utils.UUIField(db_index=True, default=uuid.uuid4, editable=False, max_length=36, unique=True, verbose_name='System ID')),
                ('name', models.CharField(max_length=50, unique=True, verbose_name='Name')),
                ('description', models.CharField(blank=True, max_length=200, null=True, verbose_name='Description')),
            ],
            options={
                'verbose_name': 'Cash Receipt Journal Batch',
                'verbose_name_plural': 'Cash Receipt Journal Batches',
                'ordering': ['name'],
            },
        ),
        migrations.AddIndex(
            model_name='cashreceiptjournalbatch',
            index=models.Index(fields=['name'], name='crj_batch_name_idx'),
        ),
        migrations.CreateModel(
            name='CashReceiptJournalLine',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('system_id', utils.utils.UUIField(db_index=True, default=uuid.uuid4, editable=False, max_length=36, unique=True, verbose_name='System ID')),
                ('batch_name', models.CharField(max_length=50, verbose_name='Batch Name')),
                ('line_no', models.IntegerField(default=10000, verbose_name='Line No.')),
                ('posting_date', models.DateField(blank=True, default=purchases.models.get_today, null=True, verbose_name='Posting Date')),
                ('document_no', models.CharField(blank=True, max_length=50, null=True, verbose_name='Document No.')),
                ('account_type', models.CharField(blank=True, choices=[('Customer', 'Customer'), ('Vendor', 'Vendor'), ('G/L Account', 'G/L Account')], default='Customer', max_length=20, null=True, verbose_name='Account Type')),
                ('account_no', models.CharField(blank=True, max_length=50, null=True, verbose_name='Account No.')),
                ('description', models.TextField(blank=True, null=True, verbose_name='Description')),
                ('amount', models.IntegerField(blank=True, null=True, verbose_name='Amount')),
                ('bal_account_type', models.CharField(blank=True, choices=[('Customer', 'Customer'), ('Vendor', 'Vendor'), ('G/L Account', 'G/L Account')], max_length=20, null=True, verbose_name='Bal. Account Type')),
                ('bal_account_no', models.CharField(blank=True, max_length=50, null=True, verbose_name='Bal. Account No.')),
                ('status', models.CharField(choices=[('Open', 'Open'), ('Posted', 'Posted'), ('Void', 'Void'), ('Cancelled', 'Cancelled')], default='Open', max_length=20, verbose_name='Status')),
                ('payment_method', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cash_receipt_lines', to='financials.paymentmethod', verbose_name='Payment Method')),
            ],
            options={
                'verbose_name': 'Cash Receipt Journal Line',
                'verbose_name_plural': 'Cash Receipt Journal Lines',
                'ordering': ['batch_name', 'line_no'],
            },
        ),
        migrations.AddIndex(
            model_name='cashreceiptjournalline',
            index=models.Index(fields=['batch_name', 'line_no'], name='crj_line_idx'),
        ),
        migrations.AddIndex(
            model_name='cashreceiptjournalline',
            index=models.Index(fields=['posting_date'], name='crj_date_idx'),
        ),
        migrations.AddIndex(
            model_name='cashreceiptjournalline',
            index=models.Index(fields=['document_no'], name='crj_doc_idx'),
        ),
        migrations.AddIndex(
            model_name='cashreceiptjournalline',
            index=models.Index(fields=['status'], name='crj_status_idx'),
        ),
    ]
