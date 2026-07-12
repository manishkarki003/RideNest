from django.contrib import admin
from .models import Vehicle, VehicleImage


class VehicleImageInline(admin.TabularInline):
    model = VehicleImage
    extra = 0


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "approval_status", "availability_status", "is_active", "created_at")
    list_filter = ("approval_status", "availability_status", "vehicle_type", "fuel_type", "is_active")
    search_fields = ("name", "brand", "model", "registration_number", "owner__username")
    prepopulated_fields = {}
    readonly_fields = ("slug", "created_at", "updated_at")
    inlines = [VehicleImageInline]
