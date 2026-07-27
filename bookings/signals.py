"""Signal handlers for the bookings app.

Sends exactly one confirmation email on the PENDING -> CONFIRMED
transition. Deliberately does not touch booking behaviour — it only
observes state changes after they've already been persisted by
Booking.confirm().
"""
from __future__ import annotations

from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from bookings.emails import send_booking_confirmation_email
from bookings.models import Booking


@receiver(pre_save, sender=Booking)
def cache_previous_booking_status(sender, instance: Booking, **kwargs) -> None:
    """
    Stashes the booking_status currently in the DB onto the instance
    before it gets overwritten, so post_save can detect the transition.
    """
    if instance.pk:
        instance._previous_booking_status = (
            Booking.objects.filter(pk=instance.pk)
            .values_list("booking_status", flat=True)
            .first()
        )
    else:
        instance._previous_booking_status = None


@receiver(post_save, sender=Booking)
def send_confirmation_email_on_confirm(sender, instance: Booking, created: bool, **kwargs) -> None:
    if created:
        # A booking is always created as PENDING; nothing to notify yet.
        return

    previous_status = getattr(instance, "_previous_booking_status", None)

    if previous_status == Booking.Status.PENDING and instance.booking_status == Booking.Status.CONFIRMED:
        # Defer until the enclosing transaction (see BookingDetailView.post,
        # which wraps confirm() in transaction.atomic()) actually commits.
        # This avoids sending an email for a confirmation that later rolls
        # back, and avoids holding the row lock open during the API call.
        transaction.on_commit(lambda: send_booking_confirmation_email(instance))