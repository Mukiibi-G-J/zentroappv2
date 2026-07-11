from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0015_restaurantstaffdevice_user_nullable"),
    ]

    operations = [
        migrations.AlterField(
            model_name="customuser",
            name="phone_number",
            field=models.CharField(max_length=20, unique=True),
        ),
    ]
