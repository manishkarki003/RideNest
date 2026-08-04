from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Prefetch
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from accounts.models import User
from vehicles.models import Vehicle, VehicleImage
from .emails import send_booking_received_email, send_owner_booking_notification
from .forms import BookingRequestForm, OwnerBookingActionForm, RenterCancellationForm
from .models import Booking


class OwnerRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self) -> bool:
        return self.request.user.role == User.Role.OWNER


class BookingHomeView(LoginRequiredMixin, View):
    def get(self, request: HttpRequest) -> HttpResponse:
        return redirect("bookings:history")


class BookingRequestView(LoginRequiredMixin, View):
    template_name = "bookings/booking_form.html"

    def get_vehicle(self, slug: str) -> Vehicle:
        return get_object_or_404(
            Vehicle.objects.marketplace_visible().select_related("owner"),
            slug=slug,
        )

    def get(self, request: HttpRequest, vehicle_slug: str) -> HttpResponse:
        vehicle = self.get_vehicle(vehicle_slug)
        if vehicle.owner_id == request.user.id:
            messages.error(request, "You cannot book your own vehicle.")
            return redirect("vehicles:public_detail", slug=vehicle.slug)

        return render(
            request,
            self.template_name,
            {
                "vehicle": vehicle,
                "form": BookingRequestForm(
                    vehicle=vehicle,
                    renter=request.user,
                ),
            },
        )

    def post(self, request: HttpRequest, vehicle_slug: str) -> HttpResponse:
        vehicle = self.get_vehicle(vehicle_slug)
        form = BookingRequestForm(
            request.POST,
            vehicle=vehicle,
            renter=request.user,
        )

        if not form.is_valid():
            return render(
                request,
                self.template_name,
                {
                    "vehicle": vehicle,
                    "form": form,
                },
            )

        try:
            with transaction.atomic():
                locked_vehicle = (
                    Vehicle.objects
                    .select_for_update()
                    .select_related("owner")
                    .get(pk=vehicle.pk)
                )

                if locked_vehicle.owner_id == request.user.id:
                    raise ValidationError("You cannot book your own vehicle.")

                if not (
                    locked_vehicle.is_active
                    and locked_vehicle.approval_status == Vehicle.ApprovalStatus.APPROVED
                    and locked_vehicle.availability_status == Vehicle.AvailabilityStatus.AVAILABLE
                ):
                    raise ValidationError(
                        "This vehicle is not currently available for booking."
                    )

                pickup_date = form.cleaned_data["pickup_date"]
                return_date = form.cleaned_data["return_date"]

                if Booking.conflicting_bookings(
                    locked_vehicle,
                    pickup_date,
                    return_date,
                ).exists():
                    raise ValidationError(
                        "These dates overlap with an existing booking request."
                    )

                booking = Booking(
                    vehicle=locked_vehicle,
                    renter=request.user,
                    pickup_date=pickup_date,
                    return_date=return_date,
                )
                booking.save()
                
                transaction.on_commit(lambda: send_booking_received_email(booking))
                transaction.on_commit(lambda: send_owner_booking_notification(booking))

        except ValidationError as error:
            form.add_error(None, error)
            return render(
                request,
                self.template_name,
                {
                    "vehicle": vehicle,
                    "form": form,
                },
            )

        messages.success(
            request,
            f"Booking request {booking.short_reference} has been submitted.",
)

        return redirect(
            "payments:payment_page",
            booking_reference=booking.booking_reference,
) 

class BookingHistoryView(LoginRequiredMixin, View):
    def get(self, request: HttpRequest) -> HttpResponse:

        bookings = (
            Booking.objects
            .filter(renter=request.user)
            .select_related("vehicle", "owner")
            .prefetch_related(
                Prefetch(
                    "vehicle__images",
                    queryset=VehicleImage.objects.order_by(
                        "-is_primary",
                        "created_at",
                    ),
                )
            )
            .order_by("-created_at")
        )

        today = timezone.localdate()

        stats = {
            "upcoming": bookings.filter(
                booking_status=Booking.Status.PENDING
            ).count(),

            "current": bookings.filter(
                booking_status=Booking.Status.CONFIRMED
            ).count(),

            "completed": bookings.filter(
                booking_status=Booking.Status.COMPLETED
            ).count(),

            "cancelled": bookings.filter(
                booking_status=Booking.Status.CANCELLED
            ).count(),
        }

        return render(
            request,
            "bookings/booking_history.html",
            {
                "bookings": bookings,
                "stats": stats,
                "today": today,
            },
        )


class BookingManageView(OwnerRequiredMixin, View):
    def get(self, request: HttpRequest) -> HttpResponse:
        bookings = (
            Booking.objects
            .filter(owner=request.user)
            .select_related("vehicle", "renter")
        )

        return render(
            request,
            "bookings/booking_manage.html",
            {"bookings": bookings},
        )


class BookingDetailView(LoginRequiredMixin, View):
    template_name = "bookings/booking_detail.html"

    def get_booking(self, request: HttpRequest, booking_reference) -> Booking:
        return get_object_or_404(
            Booking.objects
            .select_related("vehicle", "renter", "owner")
            .filter(
                Q(renter=request.user) |
                Q(owner=request.user)
            ),
            booking_reference=booking_reference,
        )

    def context(self, request: HttpRequest, booking: Booking, **extra) -> dict:
        context = {
            "booking": booking,
            "is_owner": booking.owner_id == request.user.id,
            "is_renter": booking.renter_id == request.user.id,
        }

        if (
            context["is_owner"]
            and booking.booking_status == Booking.Status.PENDING
        ):
            context["owner_action_form"] = (
                extra.get("owner_action_form")
                or OwnerBookingActionForm()
            )

        if (
            context["is_renter"]
            and booking.booking_status == Booking.Status.PENDING
        ):
            context["renter_cancellation_form"] = (
                extra.get("renter_cancellation_form")
                or RenterCancellationForm()
            )

        return context

    def get(self, request: HttpRequest, booking_reference) -> HttpResponse:
        booking = self.get_booking(request, booking_reference)
        return render(
            request,
            self.template_name,
            self.context(request, booking),
        )

    def post(self, request: HttpRequest, booking_reference) -> HttpResponse:
        booking = self.get_booking(request, booking_reference)

        try:
            with transaction.atomic():

                booking = (
                    Booking.objects
                    .select_for_update()
                    .select_related("vehicle", "renter", "owner")
                    .get(booking_reference=booking.booking_reference)
                )

                booking.vehicle = (
                    Vehicle.objects
                    .select_for_update()
                    .get(pk=booking.vehicle_id)
                )

                if booking.owner_id == request.user.id:

                    form = OwnerBookingActionForm(request.POST)

                    if not form.is_valid():
                        return render(
                            request,
                            self.template_name,
                            self.context(
                                request,
                                booking,
                                owner_action_form=form,
                            ),
                        )

                    action = form.cleaned_data["action"]

                    if action == OwnerBookingActionForm.Action.CONFIRM:
                        booking.confirm()
                        messages.success(
                            request,
                            "Booking confirmed and vehicle marked reserved.",
                        )

                    elif action == OwnerBookingActionForm.Action.REJECT:
                        booking.reject(form.cleaned_data["owner_notes"])
                        messages.success(
                            request,
                            "Booking request rejected.",
                        )

                    else:
                        booking.cancel(
                            form.cleaned_data["cancellation_reason"],
                            form.cleaned_data["owner_notes"],
                        )
                        messages.success(
                            request,
                            "Booking cancelled.",
                        )

                elif booking.renter_id == request.user.id:

                    form = RenterCancellationForm(request.POST)

                    if not form.is_valid():
                        return render(
                            request,
                            self.template_name,
                            self.context(
                                request,
                                booking,
                                renter_cancellation_form=form,
                            ),
                        )

                    if booking.booking_status != Booking.Status.PENDING:
                        raise ValidationError(
                            "Only pending bookings can be cancelled by the renter."
                        )

                    booking.cancel(
                        form.cleaned_data["cancellation_reason"]
                    )

                    messages.success(
                        request,
                        "Booking request cancelled.",
                    )

                else:
                    raise ValidationError(
                        "You do not have permission to manage this booking."
                    )

        except ValidationError as error:
            messages.error(request, error.messages[0])

            return redirect(
                "bookings:booking_detail",
                booking_reference=booking.booking_reference,
            )

            return redirect(
               "payments:payment_page",
                booking_reference=booking.booking_reference,
            )