from django.db import migrations, models


def disable_barcode_scanner_by_default(apps, schema_editor):
    MobileAppUserSettings = apps.get_model("settings", "MobileAppUserSettings")
    MobileAppUserSettings.objects.filter(barcode_scanner_enabled=True).update(
        barcode_scanner_enabled=False
    )


class Migration(migrations.Migration):

    dependencies = [
        ("settings", "0002_mobileappusersettings"),
    ]

    operations = [
        migrations.AlterField(
            model_name="mobileappusersettings",
            name="barcode_scanner_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(
            disable_barcode_scanner_by_default,
            migrations.RunPython.noop,
        ),
    ]
