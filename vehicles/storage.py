from storages.backends.s3 import S3Storage
from django.conf import settings


class SupabasePublicStorage(S3Storage):
    """
    Store files using the Supabase S3 API,
    but generate public object URLs.
    """

    def url(self, name, parameters=None, expire=None, http_method=None):
        base = settings.SUPABASE_PUBLIC_URL.rstrip("/")
        bucket = self.bucket_name
        return f"{base}/storage/v1/object/public/{bucket}/{name}"