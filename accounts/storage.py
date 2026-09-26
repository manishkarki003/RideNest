"""Storage backends for account data that must not be publicly served."""
import os

import boto3
from botocore.config import Config
from storages.backends.s3 import S3Storage


class PrivateVerificationStorage(S3Storage):
    """
    Stores identity verification documents in a private Supabase bucket.
    Files are never publicly accessible - every URL is a short-lived,
    signed S3 URL generated on demand.
    """

    def __init__(self, **kwargs):
        kwargs.setdefault("access_key", os.getenv("SUPABASE_S3_ACCESS_KEY"))
        kwargs.setdefault("secret_key", os.getenv("SUPABASE_S3_SECRET_KEY"))
        kwargs.setdefault("bucket_name", "verification-documents")
        kwargs.setdefault("endpoint_url", os.getenv("SUPABASE_S3_ENDPOINT"))
        kwargs.setdefault("region_name", os.getenv("SUPABASE_S3_REGION"))
        kwargs.setdefault("default_acl", "private")
        kwargs.setdefault("querystring_auth", True)
        kwargs.setdefault("querystring_expire", 300)
        super().__init__(**kwargs)

    def url(self, name, parameters=None, expire=None, http_method=None):
        client = boto3.client(
            "s3",
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            endpoint_url=self.endpoint_url,
            region_name=self.region_name,
            config=Config(signature_version="s3v4"),
        )
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket_name, "Key": self._normalize_name(name)},
            ExpiresIn=expire if expire is not None else self.querystring_expire,
        )