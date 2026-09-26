"""Review domain model — one review per completed booking."""
from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Avg, Count

from bookings.models import Booking
from vehicles.models import Vehicle


class ReviewQuerySet(models.QuerySet):
    def for_vehicle(self, vehicle: Vehicle):
        return self.filter(vehicle=vehicle)

    def vehicle_stats(self, vehicle: Vehicle) -> dict[str, Any]:
        result = self.for_vehicle(vehicle).aggregate(average=Avg("rating"), total=Count("id"))
        return {
            "average": round(result["average"], 1) if result["average"] is not None else None,
            "total": result["total"],
        }


class ReviewManager(models.Manager.from_queryset(ReviewQuerySet)):
    pass


class Review(models.Model):
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name="review")
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="reviews", editable=False)
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews_written", editable=False
    )
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ReviewManager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["vehicle", "created_at"], name="review_vehicle_created_idx"),
        ]

    def clean(self) -> None:
        errors: dict[str, str] = {}
        if self.booking_id and self.booking.booking_status != Booking.Status.COMPLETED:
            errors["booking"] = "You can only review a completed booking."
        if self.booking_id and self.reviewer_id and self.booking.renter_id != self.reviewer_id:
            errors["reviewer"] = "Only the renter on this booking can leave a review."
        if errors:
            raise ValidationError(errors)

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self._state.adding:
            self.vehicle = self.booking.vehicle
            self.reviewer = self.booking.renter
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.rating}★ review of {self.vehicle.name} by {self.reviewer}"