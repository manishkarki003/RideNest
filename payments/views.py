from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView

from bookings.models import Booking
from payments.enums import PaymentGateway
from payments.models import Payment
from payments.services import PaymentService


class PaymentPageView(LoginRequiredMixin, View):
    """
    Displays the payment page for a booking.
    """

    template_name = "payments/payment_page.html"

    def get(self, request, booking_reference):
        booking = get_object_or_404(
            Booking,
            booking_reference=booking_reference,
            renter=request.user,
        )

        return render(
            request,
            self.template_name,
            {
                "booking": booking,
            },
        )


class PaymentInitiateView(LoginRequiredMixin, View):
    """
    Creates a pending payment and prepares for gateway redirection.
    """

    def post(self, request, booking_reference):

        booking = get_object_or_404(
            Booking,
            booking_reference=booking_reference,
            renter=request.user,
        )
        
        gateway = request.POST.get("gateway")

        if gateway not in PaymentGateway.values:
            messages.error(request, "Please select a valid payment method.")
            return redirect(
                "payments:payment_page",
                booking_reference=booking.booking_reference,
            )

        payment = PaymentService.create_payment_for_booking(
            booking=booking,
            payer=request.user,
            amount=booking.total_amount,
            currency="NPR",
            gateway=gateway,
        )

        messages.success(
            request,
            "Payment initialized successfully.",
        )

        # Next phase:
        # Redirect to eSewa or Khalti here.

        return redirect(
            "payments:status",
            pk=payment.pk,
        )


class PaymentStatusView(LoginRequiredMixin, DetailView):
    """
    Shows payment status.
    """

    model = Payment
    context_object_name = "payment"

    def get_queryset(self):
        return Payment.objects.filter(
            Q(payer=self.request.user) | Q(booking__owner=self.request.user)
        )

    def get(self, request, *args, **kwargs):

        payment = self.get_object()

        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse(
                {
                    "payment_id": str(payment.id),
                    "booking_id": str(payment.booking_id),
                    "status": payment.status,
                    "gateway": payment.gateway,
                    "amount": str(payment.amount),
                    "currency": payment.currency,
                    "paid_at": payment.paid_at,
                }
            )

        return render(
            request,
            "payments/payment_status.html",
            {
                "payment": payment,
            },
        )