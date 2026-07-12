from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User


class RegistrationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("full_name", "username", "email", "phone_number", "address", "role")

    def clean_role(self):
        role = self.cleaned_data["role"]
        if role == User.Role.ADMIN:
            raise forms.ValidationError("Admin accounts cannot be created through registration.")
        return role
