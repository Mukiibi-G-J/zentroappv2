from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("receipt_templates", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="receipttemplate",
            name="editor_mode",
            field=models.CharField(
                choices=[
                    ("visual", "Visual (sections)"),
                    ("format_string", "Format string"),
                ],
                default="visual",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="receipttemplate",
            name="format_string",
            field=models.TextField(
                blank=True,
                default="",
                help_text="Thermal format string with {placeholders} when editor_mode is format_string.",
            ),
        ),
    ]
