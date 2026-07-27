from django.contrib import admin

from payments.models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "booking",
        "payer",
        "amount",
        "currency",
        "gateway",
        "status",
        "paid_at",
        "created_at",
    )
    list_filter = ("gateway", "status", "currency", "created_at")
    search_fields = (
        "id",
        "booking__id",
        "payer__username",
        "payer__email",
        "gateway_transaction_id",
        "gateway_reference",
    )
    readonly_fields = (
        "id",
        "gateway_transaction_id",
        "gateway_reference",
        "created_at",
        "updated_at",
    )
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    autocomplete_fields = ("booking", "payer")

    fieldsets = (
        (None, {"fields": ("id", "booking", "payer")}),
        ("Amount", {"fields": ("amount", "currency")}),
        ("Gateway", {"fields": ("gateway", "status", "gateway_transaction_id", "gateway_reference")}),
        ("Timestamps", {"fields": ("paid_at", "created_at", "updated_at")}),
    )