from django import forms
from django.core.exceptions import ValidationError
from django.db import models

from .models import Booking


class BookingRequestForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ("pickup_date", "return_date")
        widgets = {
            "pickup_date": forms.DateInput(attrs={"type": "date"}),
            "return_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, vehicle, renter, **kwargs):
        super().__init__(*args, **kwargs)
        self.vehicle = vehicle
        self.renter = renter

    def clean(self):
        cleaned_data = super().clean()
        pickup_date = cleaned_data.get("pickup_date")
        return_date = cleaned_data.get("return_date")
        if self.renter == self.vehicle.owner:
            raise ValidationError("You cannot book your own vehicle.")
        if pickup_date and return_date:
            booking = Booking(vehicle=self.vehicle, renter=self.renter, owner=self.vehicle.owner, pickup_date=pickup_date, return_date=return_date)
            try:
                booking.clean()
            except ValidationError as error:
                self.add_error(None, error)
        return cleaned_data


class OwnerBookingActionForm(forms.Form):
    class Action(models.TextChoices):
        CONFIRM = "confirm", "Confirm booking"
        REJECT = "reject", "Reject booking"
        CANCEL = "cancel", "Cancel booking"

    action = forms.ChoiceField(choices=Action.choices, widget=forms.HiddenInput)
    owner_notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
    cancellation_reason = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("action") == self.Action.CANCEL and not cleaned_data.get("cancellation_reason", "").strip():
            self.add_error("cancellation_reason", "Provide a reason when cancelling a booking.")
        return cleaned_data


class RenterCancellationForm(forms.Form):
    cancellation_reason = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}), label="Cancellation reason")
