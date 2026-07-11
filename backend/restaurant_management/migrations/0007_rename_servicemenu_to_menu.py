from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("restaurant_management", "0006_menuitem_service_menu"),
    ]

    operations = [
        migrations.RenameModel(old_name="ServiceMenu", new_name="Menu"),
        migrations.RenameModel(old_name="ServiceMenuLocation", new_name="MenuLocation"),
        migrations.RenameField(
            model_name="menuitem",
            old_name="service_menu",
            new_name="menu",
        ),
    ]
