from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('financials', '0021_financial_report_column_line_bc_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='financialreport',
            name='start_date',
            field=models.DateField(blank=True, null=True, verbose_name='Start Date'),
        ),
        migrations.AddField(
            model_name='financialreport',
            name='end_date',
            field=models.DateField(blank=True, null=True, verbose_name='End Date'),
        ),
    ]
