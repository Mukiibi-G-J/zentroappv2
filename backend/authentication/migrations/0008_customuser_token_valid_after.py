from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0007_passwordresettoken"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="token_valid_after",
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                help_text="Invalidate access tokens issued before this timestamp.",
                null=True,
            ),
        ),
    ]
