from django.db import migrations


class Migration(migrations.Migration):
    """
    0037 removed the Django UniqueConstraint unique_non_empty_serial_no, but many
    tenant schemas still have a leftover UNIQUE INDEX items_trackingspecification_serial_no_idx
    (Postgres auto-name). That blocks sales TrackingSpecification rows for serials
    that already exist from purchase/journal receipts — POS draft/charge then 400s.
    """

    dependencies = [
        ("items", "0037_relax_tracking_serial_uniqueness"),
    ]

    operations = [
        migrations.RunSQL(
            sql='DROP INDEX IF EXISTS items_trackingspecification_serial_no_idx;',
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
