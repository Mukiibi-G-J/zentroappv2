from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("authentication", "0014_restaurantstaffdevice_and_pin_set_at"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="restaurantstaffdevice",
            name="user",
            field=models.ForeignKey(
                blank=True,
                help_text="Last staff member who successfully signed in on this device.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="restaurant_staff_devices",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
