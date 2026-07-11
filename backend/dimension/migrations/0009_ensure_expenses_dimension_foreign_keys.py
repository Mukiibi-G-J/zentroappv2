# Legacy placeholder: FK repair for expenses_expense lives in
# expenses.0004_not_null_branch_dimensions (_ensure_expense_dimension_fks_if_missing)
# so ordering does not break public/tenant migration history.

from django.db import migrations


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("dimension", "0008_repair_missing_id_pk"),
        ("expenses", "0003_add_dimension_fields_to_expense"),
    ]

    operations = [
        migrations.RunPython(noop, migrations.RunPython.noop),
    ]
