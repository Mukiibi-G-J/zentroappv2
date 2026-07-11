from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0009_ensure_token_valid_after_column"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="can_switch_branch",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "When Multiple Branches is enabled: if False, user is locked to their "
                    "assigned branch (Global Dimension 1); X-Branch-Id is ignored for them."
                ),
            ),
        ),
    ]
