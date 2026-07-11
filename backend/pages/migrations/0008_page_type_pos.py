from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0007_user_name_page_fields'),
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
                ],
                default='List',
                max_length=20,
            ),
        ),
    ]
