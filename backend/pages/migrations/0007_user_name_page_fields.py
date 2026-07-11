"""Ensure User Name maps to full_name on Users/User Setup/User Settings pages."""
from django.db import migrations


def _set_field(PageControlField, page, ctrl, name, *, tab=None, caption=None):
    field = PageControlField.objects.filter(page=page, page_control=ctrl, name=name).first()
    if not field:
        return
    updates = []
    if tab is not None:
        field.tab_index = tab
        updates.append('tab_index')
    if caption is not None:
        field.caption = caption
        updates.append('caption')
    if updates:
        field.save(update_fields=updates)


def fix_user_name_fields(apps, schema_editor):
    Page = apps.get_model('pages', 'Page')
    PageControl = apps.get_model('pages', 'PageControl')
    PageControlField = apps.get_model('pages', 'PageControlField')

    for page_name, ctrl_name, field_specs in (
        (
            'UsersCard',
            'UsersCardGroup',
            (
                ('full_name', 0, 'User Name'),
                ('email', 1, 'Email'),
                ('username', 2, 'Username'),
            ),
        ),
        (
            'UsersList',
            'UsersListControl',
            (
                ('full_name', 0, 'User Name'),
                ('email', 1, 'Email'),
                ('username', 2, 'Username'),
            ),
        ),
        (
            'UserSetupList',
            'UserSetupLines',
            (
                ('user__full_name', 0, 'User Name'),
                ('user__email', 1, 'Email'),
            ),
        ),
    ):
        page = Page.objects.filter(name=page_name).first()
        if not page:
            continue
        ctrl = PageControl.objects.filter(page=page, name=ctrl_name).first()
        if not ctrl:
            continue
        for name, tab, caption in field_specs:
            _set_field(PageControlField, page, ctrl, name, tab=tab, caption=caption)
        if page_name == 'UsersCard':
            page.title_field = 'full_name'
            page.save(update_fields=['title_field'])

    settings = Page.objects.filter(name='UserSettingsCard').first()
    if settings:
        settings.title_field = 'user__full_name'
        settings.save(update_fields=['title_field'])
        prefs = PageControl.objects.filter(page=settings, name='UserSettingsPreferences').first()
        if prefs:
            for name, tab, caption in (
                ('user__full_name', 0, 'User Name'),
                ('user__email', 1, 'User ID'),
                ('role', 2, None),
                ('language', 3, None),
                ('time_zone', 4, None),
                ('teaching_tips', 5, None),
            ):
                _set_field(PageControlField, settings, prefs, name, tab=tab, caption=caption)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0006_page_list_filter'),
    ]

    operations = [
        migrations.RunPython(fix_user_name_fields, noop_reverse),
    ]
