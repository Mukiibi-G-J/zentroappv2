import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("financials", "0015_general_journal"),
    ]

    operations = [
        migrations.AddField(
            model_name="generaljournalline",
            name="application_status",
            field=models.CharField(
                blank=True,
                max_length=20,
                null=True,
                verbose_name="Application Status",
            ),
        ),
        migrations.AddField(
            model_name="generaljournalline",
            name="applies_to_doc_type",
            field=models.CharField(
                blank=True,
                max_length=20,
                null=True,
                verbose_name="Applies To Document Type",
            ),
        ),
        migrations.AddField(
            model_name="generaljournalline",
            name="applies_to_content_type",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="general_journal_line_applies_to",
                to="contenttypes.contenttype",
                verbose_name="Applies To Content Type",
            ),
        ),
        migrations.AddField(
            model_name="generaljournalline",
            name="applies_to_object_id",
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                verbose_name="Applies To Object ID",
            ),
        ),
        migrations.AddIndex(
            model_name="generaljournalline",
            index=models.Index(
                fields=["applies_to_content_type", "applies_to_object_id"],
                name="financials__applies_8f3a21_idx",
            ),
        ),
    ]
