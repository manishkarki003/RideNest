import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from bookings.models import Booking  # adjust to your actual booking app path
from payments.enums import PaymentGateway, PaymentStatus


class Payment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    booking = models.OneToOneField(
        Booking,
        on_delete=models.PROTECT,
        related_name="payment",
        help_text="The booking this payment settles.",
    )

    payer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payments",
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="NPR")

    gateway = models.CharField(max_length=20, choices=PaymentGateway.choices)
    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
    )

    gateway_transaction_id = models.CharField(
        max_length=255, blank=True, null=True, unique=True,
        help_text="ID returned by the gateway once a transaction is created/completed.",
    )
    gateway_reference = models.CharField(
        max_length=255, blank=True, null=True,
        help_text="Any secondary reference/token returned by the gateway.",
    )

    paid_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["gateway"]),
            models.Index(fields=["gateway_transaction_id"]),
        ]

    def __str__(self):
        return f"Payment {self.id} · booking {self.booking_id} · {self.status}"

    # --- State transition helpers (used by services.py) ---

    def mark_processing(self):
        self.status = PaymentStatus.PROCESSING
        self.save(update_fields=["status", "updated_at"])

    def mark_successful(self, transaction_id, reference=None, paid_at=None):
        self.status = PaymentStatus.SUCCESSFUL
        self.gateway_transaction_id = transaction_id
        if reference:
            self.gateway_reference = reference
        self.paid_at = paid_at or timezone.now()
        self.save(
            update_fields=[
                "status", "gateway_transaction_id",
                "gateway_reference", "paid_at", "updated_at",
            ]
        )

    def mark_failed(self):
        self.status = PaymentStatus.FAILED
        self.save(update_fields=["status", "updated_at"])

    def mark_refunded(self):
        self.status = PaymentStatus.REFUNDED
        self.save(update_fields=["status", "updated_at"])