from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView, PasswordChangeView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View
from .forms import (
    EmailOrUsernameAuthenticationForm,
    HostRegistrationForm,
    MemberVerificationForm,
    ProfileUpdateForm,
    RegistrationForm,
)
from .models import MemberVerification


def _register(request, form_class, template_name):
    if request.user.is_authenticated:
        return redirect("core:home")
    form = form_class(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Your account has been created successfully.")
        return redirect("core:home")
    return render(request, template_name, {"form": form})


def register(request):
    return _register(request, RegistrationForm, "accounts/register.html")


def register_host(request):
    return _register(request, HostRegistrationForm, "accounts/register_host.html")

class UserLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = EmailOrUsernameAuthenticationForm
    redirect_authenticated_user = True
    success_url = reverse_lazy("core:home")

    def form_valid(self, form):
        response = super().form_valid(form)
        if not form.cleaned_data.get("remember_me"):
            self.request.session.set_expiry(0)
        messages.success(self.request, "Welcome back.")
        return response


class UserLogoutView(LogoutView):
    def post(self, request, *args, **kwargs):
        messages.success(request, "You have been logged out successfully.")
        return super().post(request, *args, **kwargs)


class ProfileView(LoginRequiredMixin, View):
    def get(self, request):
        latest_submission = request.user.verification_submissions.first()
        return render(request, "accounts/profile.html", {"verification": latest_submission})


class ProfileUpdateView(LoginRequiredMixin, View):
    def get(self, request):
        return render(request, "accounts/profile_form.html", {"form": ProfileUpdateForm(instance=request.user)})

    def post(self, request):
        form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated.")
            return redirect("accounts:profile")
        return render(request, "accounts/profile_form.html", {"form": form})


class MemberVerificationView(LoginRequiredMixin, View):
    def get(self, request):
        submission = request.user.verification_submissions.first()
        return render(request, "accounts/verification_form.html", {"form": MemberVerificationForm(), "submission": submission})

    def post(self, request):
        latest_submission = request.user.verification_submissions.first()
        if request.user.is_verified:
            messages.info(request, "Your account has already been verified.")
            return redirect("accounts:profile")
        if latest_submission and latest_submission.status == MemberVerification.Status.PENDING:
            messages.info(request, "Your verification is already awaiting review.")
            return redirect("accounts:profile")
        form = MemberVerificationForm(request.POST, request.FILES)
        if form.is_valid():
            submission = form.save(commit=False)
            submission.user = request.user
            submission.save()
            messages.success(request, "Your verification documents have been submitted for review.")
            return redirect("accounts:profile")
        return render(request, "accounts/verification_form.html", {"form": form, "submission": latest_submission})


class UserPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    template_name = "accounts/password_change_form.html"
    success_url = reverse_lazy("accounts:password_change_done")

    def form_valid(self, form):
        messages.success(self.request, "Your password has been changed successfully.")
        return super().form_valid(form)
