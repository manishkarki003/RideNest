from django.db import models
from django.utils.translation import gettext_lazy as _


class PaymentGateway(models.TextChoices):
    KHALTI = "khalti", _("Khalti")
    ESEWA = "esewa", _("eSewa")


class PaymentStatus(models.TextChoices):
    PENDING = "pending", _("Pending")
    PROCESSING = "processing", _("Processing")
    SUCCESSFUL = "successful", _("Successful")
    FAILED = "failed", _("Failed")
    REFUNDED = "refunded", _("Refunded")