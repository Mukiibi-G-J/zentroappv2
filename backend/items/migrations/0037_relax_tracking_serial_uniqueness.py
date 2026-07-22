from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("items", "0036_itemjournal_money_decimal_fields"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="trackingspecification",
            name="unique_non_empty_serial_no",
        ),
    ]
