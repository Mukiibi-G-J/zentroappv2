from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('financials', '0018_financial_report_optional_definitions'),
    ]

    operations = [
        migrations.AddField(
            model_name='financialreportrowline',
            name='amount_type',
            field=models.CharField(
                choices=[
                    ('Net Amount', 'Net Amount'),
                    ('Debits', 'Debits'),
                    ('Credits', 'Credits'),
                    ('Debits Minus Credits', 'Debits Minus Credits'),
                    ('Credits Minus Debits', 'Credits Minus Debits'),
                ],
                default='Net Amount',
                max_length=50,
                verbose_name='Amount Type',
            ),
        ),
        migrations.AddField(
            model_name='financialreportrowline',
            name='bold',
            field=models.BooleanField(default=False, verbose_name='Bold'),
        ),
        migrations.AddField(
            model_name='financialreportrowline',
            name='indentation',
            field=models.PositiveSmallIntegerField(default=0, verbose_name='Indentation'),
        ),
        migrations.AddField(
            model_name='financialreportrowline',
            name='italic',
            field=models.BooleanField(default=False, verbose_name='Italic'),
        ),
        migrations.AddField(
            model_name='financialreportrowline',
            name='new_page',
            field=models.BooleanField(default=False, verbose_name='New Page'),
        ),
        migrations.AddField(
            model_name='financialreportrowline',
            name='row_no',
            field=models.CharField(blank=True, default='', max_length=10, verbose_name='Row No.'),
        ),
        migrations.AddField(
            model_name='financialreportrowline',
            name='show',
            field=models.CharField(
                choices=[
                    ('Yes', 'Yes'),
                    ('No', 'No'),
                    ('If Amount Not Zero', 'If Amount Not Zero'),
                ],
                default='Yes',
                max_length=50,
                verbose_name='Show',
            ),
        ),
        migrations.AddField(
            model_name='financialreportrowline',
            name='totaling_type',
            field=models.CharField(
                choices=[
                    ('Posting Accounts', 'Posting Accounts'),
                    ('Total Accounts', 'Total Accounts'),
                    ('Cash Flow Accounts', 'Cash Flow Accounts'),
                    ('Cost Type', 'Cost Type'),
                    ('Cost Object', 'Cost Object'),
                ],
                default='Posting Accounts',
                max_length=50,
                verbose_name='Totaling Type',
            ),
        ),
        migrations.AddField(
            model_name='financialreportrowline',
            name='underline',
            field=models.BooleanField(default=False, verbose_name='Underline'),
        ),
    ]
