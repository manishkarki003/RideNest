"""Database models for owner-managed vehicle listings."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils.text import slugify


MAX_IMAGE_SIZE = 5 * 1024 * 1024
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def validate_vehicle_image(image: Any) -> None:
    if image.size > MAX_IMAGE_SIZE:
        raise ValidationError("Image files must be 5 MB or smaller.")
    if Path(image.name).suffix.lower() not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError("Upload a JPG, PNG, or WebP image file.")


def validate_manufacturing_year(value: int) -> None:
    if value > date.today().year + 1:
        raise ValidationError("Enter a valid manufacturing year.")


def vehicle_image_path(instance: VehicleImage, filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    return f"vehicles/{instance.vehicle_id or 'new'}/{uuid4().hex}{suffix}"


class Vehicle(models.Model):
    class VehicleType(models.TextChoices):
        CAR = "car", "Car"
        SUV = "suv", "SUV"
        VAN = "van", "Van"
        PICKUP = "pickup", "Pickup"
        MOTORCYCLE = "motorcycle", "Motorcycle"
        SCOOTER = "scooter", "Scooter"

    class FuelType(models.TextChoices):
        PETROL = "petrol", "Petrol"
        DIESEL = "diesel", "Diesel"
        ELECTRIC = "electric", "Electric"
        HYBRID = "hybrid", "Hybrid"

    class Transmission(models.TextChoices):
        MANUAL = "manual", "Manual"
        AUTOMATIC = "automatic", "Automatic"

    class AvailabilityStatus(models.TextChoices):
        AVAILABLE = "available", "Available"
        RESERVED = "reserved", "Reserved"
        RENTED = "rented", "Rented"
        UNAVAILABLE = "unavailable", "Unavailable"

    class ApprovalStatus(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING = "pending", "Pending approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="vehicles")
    slug = models.SlugField(max_length=180, unique=True, editable=False)
    name = models.CharField(max_length=150)
    brand = models.CharField(max_length=80)
    model = models.CharField(max_length=80)
    manufacturing_year = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1900), validate_manufacturing_year]
    )
    vehicle_type = models.CharField(max_length=20, choices=VehicleType.choices)
    fuel_type = models.CharField(max_length=12, choices=FuelType.choices)
    transmission = models.CharField(max_length=12, choices=Transmission.choices)
    seats = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(100)])
    registration_number = models.CharField(max_length=50, unique=True)
    color = models.CharField(max_length=50)
    mileage = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    engine_capacity = models.PositiveIntegerField(help_text="Engine capacity in cc.", validators=[MinValueValidator(1)])
    rental_price_per_day = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    security_deposit = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    description = models.TextField()
    pickup_address = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True, validators=[MinValueValidator(Decimal("-90")), MaxValueValidator(Decimal("90"))])
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True, validators=[MinValueValidator(Decimal("-180")), MaxValueValidator(Decimal("180"))])
    availability_status = models.CharField(max_length=15, choices=AvailabilityStatus.choices, default=AvailabilityStatus.AVAILABLE)
    approval_status = models.CharField(max_length=15, choices=ApprovalStatus.choices, default=ApprovalStatus.DRAFT)
    rejection_reason = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "approval_status"], name="vehicle_owner_approval_idx"),
            models.Index(fields=["approval_status", "availability_status"], name="vehicle_status_idx"),
            models.Index(fields=["brand", "model"], name="vehicle_brand_model_idx"),
        ]
        constraints = [
            models.UniqueConstraint(Lower("registration_number"), name="vehicle_registration_ci_unique"),
        ]

    def clean(self) -> None:
        errors: dict[str, str] = {}
        if self.approval_status == self.ApprovalStatus.REJECTED and not self.rejection_reason.strip():
            errors["rejection_reason"] = "A rejection reason is required for rejected vehicles."
        if self.approval_status != self.ApprovalStatus.REJECTED and self.rejection_reason:
            errors["rejection_reason"] = "A rejection reason is only allowed for rejected vehicles."
        if errors:
            raise ValidationError(errors)

    def save(self, *args: Any, **kwargs: Any) -> None:
        original_name = None
        if self.pk:
            original_name = type(self).objects.filter(pk=self.pk).values_list("name", flat=True).first()
        if not self.slug or self.name != original_name:
            base_slug = slugify(self.name)[:170] or "vehicle"
            candidate = base_slug
            suffix = 2
            while type(self).objects.exclude(pk=self.pk).filter(slug=candidate).exists():
                candidate = f"{base_slug[:175 - len(str(suffix))]}-{suffix}"
                suffix += 1
            self.slug = candidate
        self.registration_number = self.registration_number.strip().upper()
        super().save(*args, **kwargs)

    @property
    def primary_image(self) -> VehicleImage | None:
        return self.images.filter(is_primary=True).first() or self.images.first()

    def __str__(self) -> str:
        return f"{self.name} ({self.registration_number})"


class VehicleImage(models.Model):
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to=vehicle_image_path, validators=[validate_vehicle_image])
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_primary", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["vehicle"],
                condition=Q(is_primary=True),
                name="vehicle_one_primary_image",
            ),
        ]

    def save(self, *args: Any, **kwargs: Any) -> None:
        with transaction.atomic():
            if self.is_primary and self.vehicle_id:
                type(self).objects.filter(vehicle_id=self.vehicle_id, is_primary=True).exclude(pk=self.pk).update(is_primary=False)
            super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Image for {self.vehicle.name}"
