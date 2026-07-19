from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0025_impersonationauditlog"),
    ]

    operations = [
        migrations.AddField(
            model_name="impersonationauditlog",
            name="schema_name",
            field=models.CharField(db_index=True, default="", max_length=63),
        ),
    ]
