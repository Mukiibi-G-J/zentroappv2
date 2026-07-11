"""Add must_change_password toggle field to Users card page."""
from django.db import migrations


def add_must_change_password_field(apps, schema_editor):
  PageControlField = apps.get_model('pages', 'PageControlField')
  connection = schema_editor.connection

  with connection.cursor() as cursor:
    cursor.execute(
      """
      SELECT p.page_id, c.page_control_id
      FROM page_engine_page p
      JOIN page_engine_control c ON c.page_id = p.page_id
      WHERE p.name = %s AND c.name = %s
      LIMIT 1
      """,
      ['UsersCard', 'UsersCardGroup'],
    )
    row = cursor.fetchone()
    if not row:
      return
    page_id, control_id = row

    cursor.execute(
      """
      SELECT 1
      FROM page_engine_field
      WHERE page_id = %s AND name = %s
      LIMIT 1
      """,
      [page_id, 'must_change_password'],
    )
    if cursor.fetchone():
      return

  PageControlField.objects.create(
    page_id=page_id,
    page_control_id=control_id,
    name='must_change_password',
    caption='User must change password at next login',
    field_type='Boolean',
    visible=True,
    editable=True,
    primary_key=False,
    required=False,
    tab_index=8,
    tooltip='',
    enum_values='',
    no_series_code='',
    has_table_relation=False,
    related_table='',
    related_field='',
    related_display_field='',
  )


def remove_must_change_password_field(apps, schema_editor):
  PageControlField = apps.get_model('pages', 'PageControlField')
  PageControlField.objects.filter(
    page__name='UsersCard',
    name='must_change_password',
  ).delete()


class Migration(migrations.Migration):

  dependencies = [
    ('pages', '0010_headline_group_control_type'),
  ]

  operations = [
    migrations.RunPython(add_must_change_password_field, remove_must_change_password_field),
  ]
