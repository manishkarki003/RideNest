from django.contrib import admin

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("vehicle", "reviewer", "rating", "created_at")
    list_filter = ("rating", "created_at")
    search_fields = ("vehicle__name", "reviewer__email", "comment")
    readonly_fields = ("vehicle", "reviewer", "booking", "created_at", "updated_at")