from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View
from django.views.generic import DetailView

from bookings.models import Booking  # adjust to your actual booking app path
from payments.models import Payment
from payments.services import PaymentService


class PaymentInitiateView(LoginRequiredMixin, View):
    """
    Creates (or fetches) a Pending payment for a booking.
    Actual gateway redirect/checkout URL generation comes in the next phase.
    """

    def post(self, request, booking_id):
        booking = get_object_or_404(Booking, id=booking_id)
        gateway = request.POST.get("gateway")

        payment = PaymentService.create_payment_for_booking(
            booking=booking,
            payer=request.user,
            amount=booking.total_amount,  # adjust to your actual field name
            currency="NPR",
            gateway=gateway,
        )

        return JsonResponse(
            {
                "payment_id": str(payment.id),
                "status": payment.status,
                "gateway": payment.gateway,
            },
            status=201,
        )


class PaymentStatusView(LoginRequiredMixin, DetailView):
    """Returns current payment status as JSON."""
    model = Payment

    def get(self, request, *args, **kwargs):
        payment = self.get_object()
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