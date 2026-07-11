# Generated manually for ProductionOrder source_no -> item rename

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("production", "0007_workcenter_capacity_workcenter_direct_unit_cost_and_more"),
    ]

    operations = [
        migrations.RenameField(
            model_name="productionorder",
            old_name="source_no",
            new_name="item",
        ),
    ]
