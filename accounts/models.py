from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from pathlib import Path
from uuid import uuid4
from .storage import PrivateVerificationStorage


MAX_IMAGE_SIZE = 5 * 1024 * 1024
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def validate_image_upload(image):
    """Reject oversized files and non-image file extensions before storage."""
    if image.size > MAX_IMAGE_SIZE:
        raise ValidationError("Image files must be 5 MB or smaller.")
    if Path(image.name).suffix.lower() not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError("Upload a JPG, PNG, or WebP image file.")


def profile_picture_path(instance, filename):
    return f"profiles/{uuid4().hex}{Path(filename).suffix.lower()}"


def verification_document_path(instance, filename):
    return f"verification_documents/{uuid4().hex}{Path(filename).suffix.lower()}"


class User(AbstractUser):
    class Role(models.TextChoices):
        MEMBER = "member", "Member"
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"

    full_name = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        validators=[RegexValidator(r"^[+0-9() -]*$", "Enter a valid phone number.")],
    )
    address = models.TextField(blank=True)
    profile_picture = models.ImageField(
        upload_to=profile_picture_path,
        blank=True,
        null=True,
        validators=[validate_image_upload],
    )
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.MEMBER)
    is_verified = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.role = self.Role.ADMIN
        super().save(*args, **kwargs)

    def __str__(self):
        return self.full_name or self.username


class MemberVerification(models.Model):
    class DocumentType(models.TextChoices):
        CITIZENSHIP = "citizenship", "Citizenship card"
        PASSPORT = "passport", "Passport"
        DRIVING_LICENSE = "driving_license", "Driving licence"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="verification_submissions")
    document_type = models.CharField(max_length=20, choices=DocumentType.choices)
    document_number = models.CharField(max_length=100)
    document_image = models.ImageField(
        upload_to=verification_document_path,
        validators=[validate_image_upload],
        storage=PrivateVerificationStorage(),
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"Verification for {self.user.username} ({self.get_status_display()})"
