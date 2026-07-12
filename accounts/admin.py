from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import MemberVerification, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Rental profile", {"fields": ("full_name", "phone_number", "address", "profile_picture", "role", "is_verified")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Rental profile", {"fields": ("full_name", "email", "role")}),
    )
    list_display = ("username", "email", "full_name", "role", "is_verified", "is_staff")
    list_filter = ("role", "is_verified", "is_staff")


@admin.register(MemberVerification)
class MemberVerificationAdmin(admin.ModelAdmin):
    list_display = ("user", "document_type", "status", "submitted_at")
    list_filter = ("status", "document_type")
    search_fields = ("user__username", "user__email", "document_number")
    readonly_fields = ("submitted_at",)
