from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("restaurant_management", "0002_menulayoutpage_modifiergroup_servicemenu_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="menulayouttile",
            name="accent_color",
            field=models.CharField(
                max_length=16,
                blank=True,
                default="",
                help_text="Preset key (e.g. indigo) or #RRGGBB for POS tile styling.",
            ),
        ),
    ]
