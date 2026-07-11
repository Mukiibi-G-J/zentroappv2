from settings.models import MobileAppUserSettings


class MobileAppUserSettingsRepository:
    @staticmethod
    def get_or_create_for_user(user):
        return MobileAppUserSettings.objects.select_related("user").get_or_create(
            user=user
        )
