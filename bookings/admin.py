from django.contrib import admin
from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("short_reference", "vehicle", "renter", "owner", "booking_status", "pickup_date", "return_date", "total_amount")
    list_filter = ("booking_status", "created_at")
    search_fields = ("booking_reference", "vehicle__name", "renter__username", "owner__username")
    readonly_fields = ("booking_reference", "renter", "owner", "vehicle", "pickup_date", "return_date", "total_days", "rental_price_per_day", "subtotal", "security_deposit", "total_amount", "created_at", "updated_at")
