from django.db import models
from django.utils.timezone import now

from .storage import AppVersionAPKStorage


PLATFORM_CHOICES = [
    ("android", "Android"),
    ("ios", "iOS"),
    ("windows", "Windows"),
    ("macos", "macOS"),
    ("linux", "Linux"),
    ("all", "All platforms"),
]


class AppVersion(models.Model):
    apk_storage = AppVersionAPKStorage()

    platform = models.CharField(
        max_length=10,
        choices=PLATFORM_CHOICES,
        default="android",
        db_index=True,
    )
    version_name = models.CharField(
        max_length=30,
        help_text="Human-readable version (e.g. 1.2.0). Shown in the update modal.",
    )
    build_number = models.PositiveIntegerField(
        help_text=(
            "Android versionCode / iOS CFBundleVersion integer. "
            "This is the LATEST build being released."
        ),
    )
    min_required_build = models.PositiveIntegerField(
        default=0,
        help_text=(
            "Any installed build BELOW this number is force-blocked immediately "
            "(no grace period). Set to 0 to disable hard minimum."
        ),
    )
    grace_period_days = models.PositiveIntegerField(
        default=7,
        help_text=(
            "How many days after released_at before a soft update becomes a hard block. "
            "During this window the update modal is dismissible."
        ),
    )
    released_at = models.DateTimeField(
        default=now,
        help_text="When this version was released. Grace period is counted from here.",
    )
    apk_file = models.FileField(
        upload_to="",
        storage=apk_storage,
        blank=True,
        null=True,
        help_text=(
            "Upload the installer/APK to AWS S3 (Android APK or Windows .exe). "
            "Leave blank if using an external download_url."
        ),
    )
    download_url = models.URLField(
        blank=True,
        help_text=(
            "External download or landing page URL "
            "(GitHub release, CDN, etc.). "
            "If apk_file is set, the uploaded file URL is used first. "
            "If both blank, falls back to settings.APP_LANDING_PAGE_URL."
        ),
    )
    release_notes = models.TextField(
        blank=True,
        help_text="What's new in this version. Shown in the update modal.",
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Only active versions are returned by the API.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "app_updates_appversion"
        verbose_name = "App version"
        verbose_name_plural = "App versions"
        ordering = ["-build_number"]

    def __str__(self):
        return f"v{self.version_name} (build {self.build_number}) [{self.platform}]"
