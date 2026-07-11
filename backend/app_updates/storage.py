from storages.backends.s3boto3 import S3Boto3Storage


class AppVersionAPKStorage(S3Boto3Storage):
    """
    Dedicated S3 storage for app update binaries.
    Keeps APK uploads in the bucket even if default storage varies by env.
    """

    location = "app_versions"
    file_overwrite = False
    querystring_auth = True

