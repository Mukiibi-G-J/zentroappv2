from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0014_page_desktop_enabled'),
    ]

    operations = [
        migrations.AlterField(
            model_name='page',
            name='page_type',
            field=models.CharField(
                choices=[
                    ('List', 'List'),
                    ('Card', 'Card'),
                    ('Document', 'Document'),
                    ('ListPart', 'ListPart'),
                    ('Journal', 'Journal'),
                    ('Worksheet', 'Worksheet'),
                    ('RoleCenter', 'Role Center'),
                    ('POS', 'Point of Sale'),
                    ('Queue', 'Sync Queue'),
                ],
                default='List',
                max_length=20,
            ),
        ),
    ]
