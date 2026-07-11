from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("restaurant_management", "0003_menulayouttile_accent_color"),
    ]

    operations = [
        migrations.AddField(
            model_name="menuitem",
            name="kitchen_facing_name",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Short label for kitchen tickets / KDS (often lowercase, no spaces).",
                max_length=120,
                verbose_name="Kitchen facing name",
            ),
        ),
    ]
