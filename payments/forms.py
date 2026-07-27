from django import forms

from payments.enums import PaymentGateway
from payments.models import Payment


class PaymentInitiationForm(forms.Form):
    """Used to select which gateway the payer wants to pay through."""
    gateway = forms.ChoiceField(choices=PaymentGateway.choices)


class PaymentAdminForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["booking", "payer", "amount", "currency", "gateway", "status"]