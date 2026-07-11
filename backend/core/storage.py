from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django_tenants.files.storage import TenantFileSystemStorage
from django.db import connection
from storages.backends.s3boto3 import S3Boto3Storage


class CustomSchemaStorage(TenantFileSystemStorage):
    def _get_storage_backend(self):
        scheme_name = connection.schema_name
        if settings.ENVIRONMENT == "development":
            if scheme_name == "public":
                return FileSystemStorage()
            else:
                return S3TenantStorage(scheme_name)

        else:
            if scheme_name == "public":
                return S3Boto3Storage()
            else:
                return S3TenantStorage(scheme_name)

    def save(self, name, content, max_length=None):
        storage = self._get_storage_backend()
        return storage.save(name, content, max_length)

    def generate_filename(self, name):
        storage_backend = self._get_storage_backend()
        return storage_backend.generate_filename(name)

    def url(self, name):
        storage_backend = self._get_storage_backend()
        return storage_backend.url(name)

    def delete(self, name):
        storage = self._get_storage_backend()
        return storage.delete(name)

    def exists(self, name):
        storage = self._get_storage_backend()
        return storage.exists(name)

    def open(self, name, mode="rb"):
        storage = self._get_storage_backend()
        return storage.open(name, mode)


class S3TenantStorage(S3Boto3Storage):

    def __init__(self, scheme_name):
        self.scheme_name = scheme_name
        super().__init__()
        self.bucket_name = (
            settings.AWS_STORAGE_BUCKET_NAME
        )  # Always use the real bucket name

    def save(self, name, content, max_length=None):
        # Store files under a folder named after the schema
        path = f"{self.scheme_name}/{name}"
        return super().save(path, content, max_length)
