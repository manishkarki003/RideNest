"""
Business-logic layer for Payment lifecycle management.
Gateway-specific integration (Khalti / eSewa API calls, signature
verification, webhooks) is intentionally NOT implemented here yet —
this phase only establishes the architecture.
"""

from django.db import transaction

from payments.enums import PaymentGateway, PaymentStatus
from payments.models import Payment


class PaymentService:

    @staticmethod
    @transaction.atomic
    def create_payment_for_booking(*, booking, payer, amount, currency, gateway):
        """
        Idempotently creates a Pending payment for a booking.
        Safe to call repeatedly before a gateway transaction is initiated.
        """
        if gateway not in PaymentGateway.values:
            raise ValueError(f"Unsupported gateway: {gateway}")

        payment, _created = Payment.objects.get_or_create(
            booking=booking,
            defaults={
                "payer": payer,
                "amount": amount,
                "currency": currency,
                "gateway": gateway,
                "status": PaymentStatus.PENDING,
            },
        )
        return payment

    @staticmethod
    def mark_processing(payment: Payment) -> Payment:
        payment.mark_processing()
        return payment

    @staticmethod
    def mark_successful(payment: Payment, transaction_id: str, reference: str = None) -> Payment:
        payment.mark_successful(transaction_id=transaction_id, reference=reference)
        return payment

    @staticmethod
    def mark_failed(payment: Payment) -> Payment:
        payment.mark_failed()
        return payment

    @staticmethod
    def refund(payment: Payment) -> Payment:
        payment.mark_refunded()
        return payment