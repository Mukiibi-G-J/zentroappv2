# Generated manually for Manufacturing Setup manufacturing_enabled

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("setup", "0006_resourcesetup"),
    ]

    operations = [
        migrations.AddField(
            model_name="manufacturingsetup",
            name="manufacturing_enabled",
            field=models.BooleanField(
                default=False,
                help_text="When enabled, items will show Production BOM section for defining bill of materials.",
                verbose_name="Manufacturing Enabled",
            ),
        ),
    ]
