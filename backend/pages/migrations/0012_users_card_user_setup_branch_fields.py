"""Move can_switch_branch to User Setup; ensure must_change_password on Users card."""

from django.db import migrations


def _get_control(cursor, page_name, control_name):
    cursor.execute(
        """
        SELECT p.page_id, c.page_control_id
        FROM page_engine_page p
        JOIN page_engine_control c ON c.page_id = p.page_id
        WHERE p.name = %s AND c.name = %s
        LIMIT 1
        """,
        [page_name, control_name],
    )
    return cursor.fetchone()


def _field_exists(cursor, page_id, field_name):
    cursor.execute(
        """
        SELECT 1
        FROM page_engine_field
        WHERE page_id = %s AND name = %s
        LIMIT 1
        """,
        [page_id, field_name],
    )
    return cursor.fetchone() is not None


def apply_field_changes(apps, schema_editor):
    PageControlField = apps.get_model('pages', 'PageControlField')
    connection = schema_editor.connection

    with connection.cursor() as cursor:
        users_row = _get_control(cursor, 'UsersCard', 'UsersCardGroup')
        if users_row:
            users_page_id, users_control_id = users_row
            PageControlField.objects.filter(
                page_id=users_page_id,
                page_control_id=users_control_id,
                name='can_switch_branch',
            ).delete()

            if not _field_exists(cursor, users_page_id, 'must_change_password'):
                PageControlField.objects.create(
                    page_id=users_page_id,
                    page_control_id=users_control_id,
                    name='must_change_password',
                    caption='User must change password at next login',
                    field_type='Boolean',
                    visible=True,
                    editable=True,
                    primary_key=False,
                    required=False,
                    tab_index=7,
                    tooltip='',
                    enum_values='',
                    no_series_code='',
                    has_table_relation=False,
                    related_table='',
                    related_field='',
                    related_display_field='',
                )
            else:
                PageControlField.objects.filter(
                    page_id=users_page_id,
                    page_control_id=users_control_id,
                    name='must_change_password',
                ).update(tab_index=7)

            PageControlField.objects.filter(
                page_id=users_page_id,
                page_control_id=users_control_id,
                name='password',
            ).update(tab_index=6)

        setup_row = _get_control(cursor, 'UserSetupList', 'UserSetupLines')
        if setup_row:
            setup_page_id, setup_control_id = setup_row
            if not _field_exists(cursor, setup_page_id, 'user__can_switch_branch'):
                PageControlField.objects.create(
                    page_id=setup_page_id,
                    page_control_id=setup_control_id,
                    name='user__can_switch_branch',
                    caption='Can Switch Branch',
                    field_type='Boolean',
                    visible=True,
                    editable=True,
                    primary_key=False,
                    required=False,
                    tab_index=10,
                    tooltip='',
                    enum_values='',
                    no_series_code='',
                    has_table_relation=False,
                    related_table='',
                    related_field='',
                    related_display_field='',
                )


def reverse_field_changes(apps, schema_editor):
    PageControlField = apps.get_model('pages', 'PageControlField')
    connection = schema_editor.connection

    with connection.cursor() as cursor:
        users_row = _get_control(cursor, 'UsersCard', 'UsersCardGroup')
        if users_row:
            users_page_id, users_control_id = users_row
            PageControlField.objects.filter(
                page_id=users_page_id,
                page_control_id=users_control_id,
                name='must_change_password',
            ).delete()

            if not _field_exists(cursor, users_page_id, 'can_switch_branch'):
                PageControlField.objects.create(
                    page_id=users_page_id,
                    page_control_id=users_control_id,
                    name='can_switch_branch',
                    caption='Can Switch Branch',
                    field_type='Boolean',
                    visible=True,
                    editable=True,
                    primary_key=False,
                    required=False,
                    tab_index=6,
                    tooltip='',
                    enum_values='',
                    no_series_code='',
                    has_table_relation=False,
                    related_table='',
                    related_field='',
                    related_display_field='',
                )

            PageControlField.objects.filter(
                page_id=users_page_id,
                page_control_id=users_control_id,
                name='password',
            ).update(tab_index=7)

        setup_row = _get_control(cursor, 'UserSetupList', 'UserSetupLines')
        if setup_row:
            setup_page_id, setup_control_id = setup_row
            PageControlField.objects.filter(
                page_id=setup_page_id,
                page_control_id=setup_control_id,
                name='user__can_switch_branch',
            ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0011_users_card_must_change_password'),
    ]

    operations = [
        migrations.RunPython(apply_field_changes, reverse_field_changes),
    ]
