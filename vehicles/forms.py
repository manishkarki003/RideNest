from django import forms
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet, inlineformset_factory

from .models import Vehicle, VehicleImage


class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = (
            "name", "brand", "model", "manufacturing_year", "vehicle_type", "fuel_type", "transmission",
            "seats", "registration_number", "color", "mileage", "engine_capacity", "rental_price_per_day",
            "security_deposit", "description", "pickup_address", "latitude", "longitude", "availability_status",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "manufacturing_year": forms.NumberInput(attrs={"min": 1900}),
            "rental_price_per_day": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
            "security_deposit": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
        }

    def clean_registration_number(self) -> str:
        registration_number = self.cleaned_data["registration_number"].strip().upper()
        duplicates = Vehicle.objects.filter(registration_number__iexact=registration_number).exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise ValidationError("A vehicle with this registration number already exists.")
        return registration_number


class BaseVehicleImageFormSet(BaseInlineFormSet):
    def clean(self) -> None:
        super().clean()
        if any(self.errors):
            return
        primary_count = sum(
            1 for form in self.forms
            if form.cleaned_data and not form.cleaned_data.get("DELETE") and form.cleaned_data.get("is_primary")
        )
        if primary_count > 1:
            raise ValidationError("Choose only one primary image.")


VehicleImageFormSet = inlineformset_factory(
    Vehicle,
    VehicleImage,
    fields=("image", "is_primary"),
    formset=BaseVehicleImageFormSet,
    extra=3,
    can_delete=True,
)
