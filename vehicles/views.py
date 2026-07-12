from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from accounts.models import User
from .forms import VehicleForm, VehicleImageFormSet
from .models import Vehicle


class OwnerRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restrict listing management to vehicle-owner accounts."""

    def test_func(self) -> bool:
        return self.request.user.role == User.Role.OWNER


class MyVehiclesView(OwnerRequiredMixin, View):
    def get(self, request: HttpRequest) -> HttpResponse:
        vehicles = Vehicle.objects.filter(owner=request.user).prefetch_related("images")
        return render(request, "vehicles/my_vehicles.html", {"vehicles": vehicles})


class VehicleCreateView(OwnerRequiredMixin, View):
    template_name = "vehicles/vehicle_form.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        form = VehicleForm()
        image_formset = VehicleImageFormSet(prefix="images")
        return render(request, self.template_name, {"form": form, "image_formset": image_formset, "page_title": "Add vehicle"})

    def post(self, request: HttpRequest) -> HttpResponse:
        form = VehicleForm(request.POST)
        vehicle = Vehicle(owner=request.user)
        image_formset = VehicleImageFormSet(request.POST, request.FILES, instance=vehicle, prefix="images")
        if form.is_valid() and image_formset.is_valid():
            vehicle = form.save(commit=False)
            vehicle.owner = request.user
            vehicle.save()
            image_formset.instance = vehicle
            image_formset.save()
            messages.success(request, "Vehicle saved as a draft. Add details or submit it for approval when ready.")
            return redirect("vehicles:detail", slug=vehicle.slug)
        return render(request, self.template_name, {"form": form, "image_formset": image_formset, "page_title": "Add vehicle"})


class OwnedVehicleMixin(OwnerRequiredMixin):
    def get_vehicle(self) -> Vehicle:
        return get_object_or_404(Vehicle.objects.prefetch_related("images"), owner=self.request.user, slug=self.kwargs["slug"])


class VehicleDetailView(OwnedVehicleMixin, View):
    def get(self, request: HttpRequest, slug: str) -> HttpResponse:
        return render(request, "vehicles/vehicle_detail.html", {"vehicle": self.get_vehicle()})


class VehicleUpdateView(OwnedVehicleMixin, View):
    template_name = "vehicles/vehicle_form.html"

    def get(self, request: HttpRequest, slug: str) -> HttpResponse:
        vehicle = self.get_vehicle()
        if vehicle.approval_status not in {Vehicle.ApprovalStatus.DRAFT, Vehicle.ApprovalStatus.REJECTED}:
            messages.info(request, "Only draft or rejected vehicles can be edited.")
            return redirect("vehicles:detail", slug=vehicle.slug)
        return render(request, self.template_name, {
            "form": VehicleForm(instance=vehicle),
            "image_formset": VehicleImageFormSet(instance=vehicle, prefix="images"),
            "vehicle": vehicle,
            "page_title": "Edit vehicle",
        })

    def post(self, request: HttpRequest, slug: str) -> HttpResponse:
        vehicle = self.get_vehicle()
        if vehicle.approval_status not in {Vehicle.ApprovalStatus.DRAFT, Vehicle.ApprovalStatus.REJECTED}:
            messages.error(request, "This vehicle cannot be edited in its current approval state.")
            return redirect("vehicles:detail", slug=vehicle.slug)
        form = VehicleForm(request.POST, instance=vehicle)
        image_formset = VehicleImageFormSet(request.POST, request.FILES, instance=vehicle, prefix="images")
        if form.is_valid() and image_formset.is_valid():
            form.save()
            image_formset.save()
            messages.success(request, "Vehicle details have been updated.")
            return redirect("vehicles:detail", slug=vehicle.slug)
        return render(request, self.template_name, {"form": form, "image_formset": image_formset, "vehicle": vehicle, "page_title": "Edit vehicle"})


class VehicleDeleteView(OwnedVehicleMixin, View):
    def post(self, request: HttpRequest, slug: str) -> HttpResponse:
        vehicle = self.get_vehicle()
        if vehicle.approval_status != Vehicle.ApprovalStatus.DRAFT:
            messages.error(request, "Only draft vehicles can be deleted.")
            return redirect("vehicles:detail", slug=vehicle.slug)
        vehicle.delete()
        messages.success(request, "Draft vehicle deleted.")
        return redirect("vehicles:mine")


class VehicleSubmitView(OwnedVehicleMixin, View):
    def post(self, request: HttpRequest, slug: str) -> HttpResponse:
        vehicle = self.get_vehicle()
        if vehicle.approval_status not in {Vehicle.ApprovalStatus.DRAFT, Vehicle.ApprovalStatus.REJECTED}:
            messages.error(request, "This vehicle cannot be submitted in its current approval state.")
            return redirect("vehicles:detail", slug=vehicle.slug)
        if not vehicle.images.exists():
            messages.error(request, "Add at least one vehicle image before submitting for approval.")
            return redirect("vehicles:detail", slug=vehicle.slug)
        vehicle.approval_status = Vehicle.ApprovalStatus.PENDING
        vehicle.rejection_reason = ""
        vehicle.save(update_fields=["approval_status", "rejection_reason", "updated_at"])
        messages.success(request, "Vehicle submitted for admin approval.")
        return redirect("vehicles:detail", slug=vehicle.slug)
