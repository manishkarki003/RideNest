"""Storage backends for account data that must not be publicly served."""
from django.conf import settings
from django.core.files.storage import FileSystemStorage


class PrivateVerificationStorage(FileSystemStorage):
    """Keep identity documents outside MEDIA_ROOT and without a public URL."""

    def __init__(self):
        super().__init__(location=settings.BASE_DIR / "private_media")

    def url(self, name):
        raise ValueError("Private verification documents do not have public URLs.")
