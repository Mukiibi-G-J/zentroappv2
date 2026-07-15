"""User Settings: User Name and User ID use login username, not full_name/email."""
from django.db import migrations


def _fix_user_settings_fields(apps, schema_editor):
    Page = apps.get_model('pages', 'Page')
    PageControl = apps.get_model('pages', 'PageControl')
    PageControlField = apps.get_model('pages', 'PageControlField')

    def retarget(page_name, ctrl_name, old_name, new_name, caption, field_type='Code', primary_key=False):
        page = Page.objects.filter(name=page_name).first()
        if not page:
            return
        ctrl = PageControl.objects.filter(page=page, name=ctrl_name).first()
        if not ctrl:
            return
        field = PageControlField.objects.filter(
            page=page, page_control=ctrl, name=old_name,
        ).first()
        if not field:
            field = PageControlField.objects.filter(
                page=page, page_control=ctrl, caption=caption,
            ).first()
        if not field:
            return
        field.name = new_name
        field.caption = caption
        field.field_type = field_type
        field.primary_key = primary_key
        field.editable = False
        field.save(update_fields=['name', 'caption', 'field_type', 'primary_key', 'editable'])

    card = Page.objects.filter(name='UserSettingsCard').first()
    if card:
        card.title_field = 'user__username'
        card.save(update_fields=['title_field'])

    retarget('UserSettingsCard', 'UserSettingsPreferences', 'user__full_name', 'user__username', 'User Name')
    retarget('UserSettingsCard', 'UserSettingsPreferences', 'user__email', 'user_id', 'User ID')

    list_page = Page.objects.filter(name='UserSettingsList').first()
    if list_page:
        list_ctrl = PageControl.objects.filter(page=list_page, name='UserSettingsListControl').first()
        if list_ctrl:
            retarget('UserSettingsList', 'UserSettingsListControl', 'user__full_name', 'user__username', 'User Name', primary_key=True)
            retarget('UserSettingsList', 'UserSettingsListControl', 'user__email', 'user_id', 'User ID')


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0015_page_type_queue'),
    ]

    operations = [
        migrations.RunPython(_fix_user_settings_fields, noop_reverse),
    ]
