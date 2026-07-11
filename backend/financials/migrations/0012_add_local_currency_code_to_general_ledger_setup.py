from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("financials", "0011_not_null_branch_dimensions"),
    ]

    operations = [
        migrations.AddField(
            model_name="generalledgersetup",
            name="local_currency_code",
            field=models.CharField(
                default="UGX",
                help_text="ISO 4217 code for local currency (LCY).",
                max_length=3,
                verbose_name="Local Currency Code",
            ),
        ),
    ]
