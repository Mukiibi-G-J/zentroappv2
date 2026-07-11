from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0010_customuser_can_switch_branch"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="restaurant_pin_hash",
            field=models.CharField(
                blank=True,
                help_text="Hashed restaurant/POS PIN for mobile quick login. Must be unique among active users with a PIN set within the tenant.",
                max_length=128,
                null=True,
            ),
        ),
    ]
