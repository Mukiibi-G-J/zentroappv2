from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('financials', '0019_financial_report_row_line_bc_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='financialreportrowline',
            name='row_amount_basis',
            field=models.CharField(
                choices=[
                    ('Net Change', 'Net Change'),
                    ('Balance at Date', 'Balance at Date'),
                    ('Beginning Balance', 'Beginning Balance'),
                ],
                default='Net Change',
                max_length=50,
                verbose_name='Row Type',
            ),
        ),
        migrations.AlterField(
            model_name='financialreportrowline',
            name='row_type',
            field=models.CharField(
                choices=[
                    ('Header', 'Header'),
                    ('Posting', 'Posting'),
                    ('Total', 'Total'),
                    ('Begin-Total', 'Begin-Total'),
                    ('End-Total', 'End-Total'),
                ],
                default='Posting',
                max_length=50,
                verbose_name='Line Type',
            ),
        ),
        migrations.AlterField(
            model_name='financialreportrowline',
            name='totaling_type',
            field=models.CharField(
                choices=[
                    ('Posting Accounts', 'Posting Accounts'),
                    ('Total Accounts', 'Total Accounts'),
                    ('Formula', 'Formula'),
                    ('Set Base For Percent', 'Set Base For Percent'),
                    ('Cash Flow Accounts', 'Cash Flow Accounts'),
                    ('Cost Type', 'Cost Type'),
                    ('Cost Object', 'Cost Object'),
                ],
                default='Posting Accounts',
                max_length=50,
                verbose_name='Totaling Type',
            ),
        ),
    ]
