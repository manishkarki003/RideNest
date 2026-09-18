from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError
from .models import MemberVerification, User


class RegistrationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("full_name", "username", "email", "phone_number", "address")
        widgets = {"address": forms.Textarea(attrs={"rows": 3})}

    role = User.Role.MEMBER

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email address already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = self.role
        if commit:
            user.save()
        return user


class HostRegistrationForm(RegistrationForm):
    role = User.Role.OWNER

class EmailOrUsernameAuthenticationForm(AuthenticationForm):
    username = forms.CharField(label="Username or email", widget=forms.TextInput(attrs={"autofocus": True}))
    remember_me = forms.BooleanField(required=False, label="Remember me")

    error_messages = {
        "invalid_login": "Enter a correct username or email and password.",
        "inactive": "This account is inactive. Please contact support.",
    }

    def clean(self):
        identifier = self.cleaned_data.get("username", "").strip()
        password = self.cleaned_data.get("password")
        if identifier and password:
            user = User.objects.filter(email__iexact=identifier).first()
            username = user.username if user else identifier
            self.user_cache = authenticate(self.request, username=username, password=password)
            if self.user_cache is None:
                raise self.get_invalid_login_error()
            self.confirm_login_allowed(self.user_cache)
        return self.cleaned_data


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("full_name", "email", "phone_number", "address", "profile_picture")
        widgets = {"address": forms.Textarea(attrs={"rows": 4})}

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise ValidationError("Another account already uses this email address.")
        return email


class MemberVerificationForm(forms.ModelForm):
    class Meta:
        model = MemberVerification
        fields = ("document_type", "document_number", "document_image")

    def clean_document_number(self):
        return self.cleaned_data["document_number"].strip()
