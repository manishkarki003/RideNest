from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from bookings.models import Booking


class Command(BaseCommand):
    help = "Marks confirmed bookings as completed once their return date has passed."

    def handle(self, *args, **options):
        today = timezone.localdate()
        due = Booking.objects.select_related("vehicle").filter(
            booking_status=Booking.Status.CONFIRMED,
            return_date__lt=today,
        )
        count = 0
        with transaction.atomic():
            for booking in due.select_for_update():
                booking.booking_status = Booking.Status.COMPLETED
                booking.save(update_fields=["booking_status", "updated_at"])
                booking._sync_vehicle_availability()
                count += 1
        self.stdout.write(f"Completed {count} booking(s).")