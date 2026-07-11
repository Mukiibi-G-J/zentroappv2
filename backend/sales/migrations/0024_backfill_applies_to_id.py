from django.db import migrations


def forwards(apps, schema_editor):
    from financials.ledger_application import backfill_customer_ledger_applies_to_ids

    backfill_customer_ledger_applies_to_ids(using=schema_editor.connection.alias)


def backwards(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0023_customerledgerentry_applies_to_id_code"),
        ("payments", "0002_payment_lines_cash_receipt"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
