"""Booking domain models with server-side price snapshots and conflict controls."""
from __future__ import annotations

from datetime import date
from typing import Any
import uuid
from django.utils import timezone

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from vehicles.models import Vehicle


class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"

    BLOCKING_STATUSES = (Status.PENDING, Status.CONFIRMED)

    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name="bookings")
    renter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="rental_bookings")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_vehicle_bookings")
    booking_reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    pickup_date = models.DateField()
    return_date = models.DateField()
    total_days = models.PositiveIntegerField(editable=False)
    rental_price_per_day = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    security_deposit = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    booking_status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    owner_notes = models.TextField(blank=True)
    cancellation_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["vehicle", "booking_status", "pickup_date", "return_date"], name="booking_vehicle_dates_idx"),
            models.Index(fields=["renter", "booking_status"], name="booking_renter_status_idx"),
            models.Index(fields=["owner", "booking_status"], name="booking_owner_status_idx"),
        ]

    @classmethod
    def conflicting_bookings(cls, vehicle: Vehicle, pickup_date: date, return_date: date, exclude_reference: uuid.UUID | None = None):
        queryset = cls.objects.filter(
            vehicle=vehicle,
            booking_status__in=cls.BLOCKING_STATUSES,
            pickup_date__lt=return_date,
            return_date__gt=pickup_date,
        )
        if exclude_reference:
            queryset = queryset.exclude(booking_reference=exclude_reference)
        return queryset

    def clean(self) -> None:
        errors: dict[str, str] = {}
        if self.renter_id and self.owner_id and self.renter_id == self.owner_id:
            errors["renter"] = "You cannot book your own vehicle."
        if self.pickup_date and self.return_date:
            if self.pickup_date < date.today():
                errors["pickup_date"] = "Pickup date cannot be in the past."
            if self.return_date <= self.pickup_date:
                errors["return_date"] = "Return date must be after the pickup date."
            elif self.vehicle_id and self.booking_status in self.BLOCKING_STATUSES:
                if self.conflicting_bookings(self.vehicle, self.pickup_date, self.return_date, self.booking_reference).exists():
                    errors["pickup_date"] = "These dates overlap with an existing booking request."
        if errors:
            raise ValidationError(errors)

    def calculate_totals(self) -> None:
        self.total_days = (self.return_date - self.pickup_date).days
        self.rental_price_per_day = self.vehicle.rental_price_per_day
        self.subtotal = self.rental_price_per_day * self.total_days
        self.security_deposit = self.vehicle.security_deposit
        self.total_amount = self.subtotal + self.security_deposit

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self._state.adding:
            self.owner = self.vehicle.owner
            self.calculate_totals()
        super().save(*args, **kwargs)

    @property
    def short_reference(self) -> str:
        return str(self.booking_reference).split("-")[0].upper()

    def _sync_vehicle_availability(self) -> None:
        has_confirmed_booking = type(self).objects.filter(
            vehicle=self.vehicle,
            booking_status=self.Status.CONFIRMED,
        ).exists()
        expected_status = Vehicle.AvailabilityStatus.RESERVED if has_confirmed_booking else Vehicle.AvailabilityStatus.AVAILABLE
        if self.vehicle.availability_status != expected_status:
            self.vehicle.availability_status = expected_status
            self.vehicle.save(update_fields=["availability_status", "updated_at"])

    def confirm(self) -> None:
        if self.booking_status != self.Status.PENDING:
            raise ValidationError("Only pending bookings can be confirmed.")
        if self.conflicting_bookings(self.vehicle, self.pickup_date, self.return_date, self.booking_reference).filter(
            booking_status=self.Status.CONFIRMED
        ).exists():
            raise ValidationError("This vehicle already has a confirmed booking for these dates.")
        self.booking_status = self.Status.CONFIRMED
        self.save(update_fields=["booking_status", "updated_at"])
        self._sync_vehicle_availability()

    def reject(self, owner_notes: str = "") -> None:
        if self.booking_status != self.Status.PENDING:
            raise ValidationError("Only pending bookings can be rejected.")
        self.booking_status = self.Status.REJECTED
        self.owner_notes = owner_notes
        self.save(update_fields=["booking_status", "owner_notes", "updated_at"])
        self._sync_vehicle_availability()

    def cancel(self, reason: str = "", owner_notes: str | None = None) -> None:
        if self.booking_status not in {self.Status.PENDING, self.Status.CONFIRMED}:
            raise ValidationError("Only pending or confirmed bookings can be cancelled.")
        self.booking_status = self.Status.CANCELLED
        self.cancellation_reason = reason
        if owner_notes is not None:
            self.owner_notes = owner_notes
        self.save(update_fields=["booking_status", "cancellation_reason", "owner_notes", "updated_at"])
        self._sync_vehicle_availability()
        

    @property
    def display_status(self):
        today = timezone.localdate()

        if self.booking_status == self.Status.CANCELLED:
            return "cancelled"

        if self.booking_status == self.Status.COMPLETED:
            return "completed"

        if self.pickup_date <= today <= self.return_date:
            return "current"

        return "upcoming"

    def __str__(self) -> str:
        return f"Booking {self.short_reference} for {self.vehicle.name}"


