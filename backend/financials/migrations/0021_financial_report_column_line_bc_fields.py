from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('financials', '0020_financial_report_row_line_formula'),
    ]

    operations = [
        migrations.AddField(
            model_name='financialreportcolumnline',
            name='column_no',
            field=models.CharField(blank=True, default='', max_length=10, verbose_name='Column No.'),
        ),
        migrations.AddField(
            model_name='financialreportcolumnline',
            name='amount_type',
            field=models.CharField(
                blank=True,
                choices=[
                    ('Net Amount', 'Net Amount'),
                    ('Debits', 'Debits'),
                    ('Credits', 'Credits'),
                    ('Debits Minus Credits', 'Debits Minus Credits'),
                    ('Credits Minus Debits', 'Credits Minus Debits'),
                ],
                default='',
                max_length=50,
                verbose_name='Amount Type',
            ),
        ),
        migrations.AddField(
            model_name='financialreportcolumnline',
            name='formula',
            field=models.CharField(blank=True, default='', max_length=80, verbose_name='Formula'),
        ),
        migrations.AddField(
            model_name='financialreportcolumnline',
            name='comparison_period_formula',
            field=models.CharField(
                blank=True,
                default='0M',
                help_text='BC-style period shift, e.g. 0M (this month), -1M (last month), 0Y (this year).',
                max_length=20,
                verbose_name='Comparison Period Formula',
            ),
        ),
        migrations.AddField(
            model_name='financialreportcolumnline',
            name='show_opposite_sign',
            field=models.BooleanField(default=False, verbose_name='Show Opposite Sign'),
        ),
    ]
