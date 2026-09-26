from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import HttpRequest, HttpResponse
from django.core.paginator import Paginator
from django.db.models import Case, F, IntegerField, Prefetch, Q, Value, When
from django.db.models.functions import Abs
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from decimal import Decimal, InvalidOperation
import json

from accounts.models import User
from .forms import VehicleForm, VehicleImageFormSet
from .models import Vehicle, VehicleImage
from bookings.models import Booking
from reviews.models import Review


PUBLIC_PAGE_SIZE = 12
SORT_OPTIONS = {
    "newest": "-created_at",
    "oldest": "created_at",
    "price_low": "rental_price_per_day",
    "price_high": "-rental_price_per_day",
    "alphabetical": "name",
}


def public_vehicle_queryset():
    return Vehicle.objects.marketplace_visible().select_related("owner").prefetch_related(
        Prefetch("images", queryset=VehicleImage.objects.only("id", "vehicle_id", "image", "is_primary", "created_at"))
    )


def valid_choice(value: str, choices: list[tuple[str, str]]) -> str:
    return value if value in {choice[0] for choice in choices} else ""


def decimal_param(value: str) -> Decimal | None:
    try:
        return Decimal(value) if value else None
    except (InvalidOperation, ValueError):
        return None


def integer_param(value: str) -> int | None:
    try:
        return int(value) if value else None
    except (TypeError, ValueError):
        return None


class MarketplaceView(View):
    template_name = "vehicles/marketplace.html"

    def get(self, request: HttpRequest, is_search_results: bool = False) -> HttpResponse:
        vehicles = public_vehicle_queryset()
        brands = list(vehicles.order_by("brand").values_list("brand", flat=True).distinct())
        query = request.GET.get("q", "").strip()
        if query:
            vehicles = vehicles.filter(
                Q(name__icontains=query) | Q(brand__icontains=query) | Q(model__icontains=query)
                | Q(description__icontains=query) | Q(pickup_address__icontains=query)
            )
        vehicle_type = valid_choice(request.GET.get("vehicle_type", ""), Vehicle.VehicleType.choices)
        fuel_type = valid_choice(request.GET.get("fuel_type", ""), Vehicle.FuelType.choices)
        transmission = valid_choice(request.GET.get("transmission", ""), Vehicle.Transmission.choices)
        availability = valid_choice(request.GET.get("availability", ""), Vehicle.AvailabilityStatus.choices)
        brand = request.GET.get("brand", "")
        seats = integer_param(request.GET.get("seats", ""))
        min_price = decimal_param(request.GET.get("min_price", ""))
        max_price = decimal_param(request.GET.get("max_price", ""))
        min_year = integer_param(request.GET.get("min_year", ""))
        max_year = integer_param(request.GET.get("max_year", ""))
        if vehicle_type:
            vehicles = vehicles.filter(vehicle_type=vehicle_type)
        if fuel_type:
            vehicles = vehicles.filter(fuel_type=fuel_type)
        if transmission:
            vehicles = vehicles.filter(transmission=transmission)
        if availability:
            vehicles = vehicles.filter(availability_status=availability)
        if brand in brands:
            vehicles = vehicles.filter(brand=brand)
        if seats and seats > 0:
            vehicles = vehicles.filter(seats=seats)
        if min_price is not None and min_price >= 0:
            vehicles = vehicles.filter(rental_price_per_day__gte=min_price)
        if max_price is not None and max_price >= 0:
            vehicles = vehicles.filter(rental_price_per_day__lte=max_price)
        if min_year:
            vehicles = vehicles.filter(manufacturing_year__gte=min_year)
        if max_year:
            vehicles = vehicles.filter(manufacturing_year__lte=max_year)
        sort = request.GET.get("sort", "newest")
        sort = sort if sort in SORT_OPTIONS else "newest"
        vehicles = vehicles.order_by(SORT_OPTIONS[sort])
        page_obj = Paginator(vehicles, PUBLIC_PAGE_SIZE).get_page(request.GET.get("page"))
        params = request.GET.copy()
        params.pop("page", None)
        page_querystring = params.urlencode()
        return render(request, self.template_name, {
            "page_obj": page_obj,
            "vehicles": page_obj.object_list,
            "brands": brands,
            "vehicle_types": Vehicle.VehicleType.choices,
            "fuel_types": Vehicle.FuelType.choices,
            "transmissions": Vehicle.Transmission.choices,
            "availability_options": Vehicle.AvailabilityStatus.choices,
            "selected_sort": sort,
            "page_querystring": page_querystring,
            "search_results": is_search_results or bool(query),
            "query": query,
            "canonical_url": request.build_absolute_uri(request.path),
        })


class PublicVehicleDetailView(View):
    def get(self, request: HttpRequest, slug: str) -> HttpResponse:
        vehicle = get_object_or_404(public_vehicle_queryset(), slug=slug)
        related = public_vehicle_queryset().exclude(pk=vehicle.pk).filter(
            Q(brand=vehicle.brand) | Q(vehicle_type=vehicle.vehicle_type)
        ).annotate(
            brand_match=Case(When(brand=vehicle.brand, then=Value(0)), default=Value(1), output_field=IntegerField()),
            type_match=Case(When(vehicle_type=vehicle.vehicle_type, then=Value(0)), default=Value(1), output_field=IntegerField()),
            price_difference=Abs(F("rental_price_per_day") - vehicle.rental_price_per_day),
        ).order_by("brand_match", "type_match", "price_difference", "-created_at")[:4]
        primary_image = vehicle.primary_image
        schema = {
            "@context": "https://schema.org",
            "@type": "Vehicle",
            "name": vehicle.name,
            "brand": {"@type": "Brand", "name": vehicle.brand},
            "model": vehicle.model,
            "vehicleConfiguration": vehicle.get_vehicle_type_display(),
            "fuelType": vehicle.get_fuel_type_display(),
            "vehicleTransmission": vehicle.get_transmission_display(),
            "productionDate": str(vehicle.manufacturing_year),
            "description": vehicle.description,
            "offers": {"@type": "Offer", "price": str(vehicle.rental_price_per_day), "priceCurrency": "NPR", "availability": "https://schema.org/InStock"},
        }
        schema_json = json.dumps(schema, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")

        reviews = Review.objects.for_vehicle(vehicle).select_related("reviewer")
        review_stats = Review.objects.vehicle_stats(vehicle)

        reviewable_booking = None
        if request.user.is_authenticated:
            reviewable_booking = Booking.objects.filter(
                vehicle=vehicle,
                renter=request.user,
                booking_status=Booking.Status.COMPLETED,
                review__isnull=True,
            ).order_by("-return_date").first()

        return render(request, "vehicles/public_vehicle_detail.html", {
            "vehicle": vehicle,
            "related_vehicles": related,
            "canonical_url": request.build_absolute_uri(request.path),
            "og_image_url": request.build_absolute_uri(primary_image.image.url) if primary_image else "",
            "vehicle_schema": schema_json,
            "reviews": reviews,
            "review_average": review_stats["average"],
            "review_count": review_stats["total"],
            "reviewable_booking": reviewable_booking,
        })


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
