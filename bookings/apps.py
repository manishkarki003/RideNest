from django.apps import AppConfig


class BookingsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "bookings"

    def ready(self) -> None:
        from bookings import signals  # noqa: F401  (registers signal receivers)