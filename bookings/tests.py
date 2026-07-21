from datetime import timedelta
from decimal import Decimal
from uuid import UUID

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from vehicles.models import Vehicle
from .models import Booking


class BookingTestCase(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(username="owner-booking", email="owner.booking@example.com", full_name="Owner", password="SafePassword123!", role="owner")
        self.renter = user_model.objects.create_user(username="renter", email="renter@example.com", full_name="Renter", password="SafePassword123!")
        self.second_renter = user_model.objects.create_user(username="renter-two", email="renter.two@example.com", full_name="Second Renter", password="SafePassword123!")
        self.other_owner = user_model.objects.create_user(username="other-owner", email="other.owner@example.com", full_name="Other Owner", password="SafePassword123!", role="owner")
        self.vehicle = self.create_vehicle()
        self.pickup_date = timezone.localdate() + timedelta(days=2)
        self.return_date = timezone.localdate() + timedelta(days=5)

    def create_vehicle(self, **overrides):
        data = {
            "owner": self.owner, "name": "Bookable SUV", "brand": "Toyota", "model": "RAV4", "manufacturing_year": 2024,
            "vehicle_type": Vehicle.VehicleType.SUV, "fuel_type": Vehicle.FuelType.PETROL,
            "transmission": Vehicle.Transmission.AUTOMATIC, "seats": 5, "registration_number": "BA 9 PA 1001",
            "color": "Blue", "mileage": 5000, "engine_capacity": 2000, "rental_price_per_day": Decimal("5000.00"),
            "security_deposit": Decimal("12000.00"), "description": "Ready to rent.", "pickup_address": "Kathmandu",
            "approval_status": Vehicle.ApprovalStatus.APPROVED, "availability_status": Vehicle.AvailabilityStatus.AVAILABLE,
            "is_active": True,
        }
        data.update(overrides)
        vehicle = Vehicle(**data)
        vehicle.save()
        return vehicle

    def request_booking(self, user=None, pickup_date=None, return_date=None):
        self.client.force_login(user or self.renter)
        return self.client.post(reverse("bookings:request", kwargs={"vehicle_slug": self.vehicle.slug}), {
            "pickup_date": pickup_date or self.pickup_date,
            "return_date": return_date or self.return_date,
        })


class BookingRequestTests(BookingTestCase):
    def test_successful_booking_uses_server_calculated_prices_and_uuid(self):
        response = self.request_booking()
        booking = Booking.objects.get()
        self.assertRedirects(response, reverse("bookings:booking_detail", kwargs={"booking_reference": booking.booking_reference}))
        self.assertIsInstance(booking.booking_reference, UUID)
        self.assertEqual(booking.owner, self.owner)
        self.assertEqual(booking.total_days, 3)
        self.assertEqual(booking.rental_price_per_day, Decimal("5000.00"))
        self.assertEqual(booking.subtotal, Decimal("15000.00"))
        self.assertEqual(booking.security_deposit, Decimal("12000.00"))
        self.assertEqual(booking.total_amount, Decimal("27000.00"))
        self.assertEqual(booking.short_reference, str(booking.booking_reference).split("-")[0].upper())
        self.vehicle.rental_price_per_day = Decimal("99999.00")
        self.vehicle.save()
        booking.refresh_from_db()
        self.assertEqual(booking.rental_price_per_day, Decimal("5000.00"))

    def test_overlapping_booking_requests_are_prevented(self):
        self.request_booking()
        response = self.request_booking(self.second_renter, self.pickup_date + timedelta(days=1), self.return_date + timedelta(days=1))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "overlap")
        self.assertEqual(Booking.objects.count(), 1)

    def test_self_booking_and_invalid_dates_are_rejected(self):
        response = self.request_booking(self.owner)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "cannot book your own")
        response = self.request_booking(self.renter, self.pickup_date, self.pickup_date)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Return date must be after")

    def test_uuid_references_are_unique_and_integer_urls_do_not_resolve(self):
        first_response = self.request_booking()
        first = Booking.objects.get()
        second_vehicle = self.create_vehicle(name="Second SUV", registration_number="BA 9 PA 1002")
        self.client.force_login(self.second_renter)
        self.client.post(reverse("bookings:request", kwargs={"vehicle_slug": second_vehicle.slug}), {
            "pickup_date": self.pickup_date, "return_date": self.return_date,
        })
        second = Booking.objects.exclude(pk=first.pk).get()
        self.assertNotEqual(first.booking_reference, second.booking_reference)
        self.assertRedirects(
            first_response,
            reverse("bookings:booking_detail", kwargs={"booking_reference": first.booking_reference}),
            fetch_redirect_response=False,
        )
        self.assertEqual(self.client.get("/bookings/1/").status_code, 404)


class BookingWorkflowTests(BookingTestCase):
    def create_booking(self):
        self.request_booking()
        return Booking.objects.get()

    def test_owner_can_confirm_and_cancel_booking_with_vehicle_status_sync(self):
        booking = self.create_booking()
        self.client.force_login(self.owner)
        response = self.client.post(reverse("bookings:booking_detail", kwargs={"booking_reference": booking.booking_reference}), {"action": "confirm", "owner_notes": "Approved"})
        self.assertRedirects(response, reverse("bookings:booking_detail", kwargs={"booking_reference": booking.booking_reference}))
        booking.refresh_from_db()
        self.vehicle.refresh_from_db()
        self.assertEqual(booking.booking_status, Booking.Status.CONFIRMED)
        self.assertEqual(self.vehicle.availability_status, Vehicle.AvailabilityStatus.RESERVED)
        self.client.post(reverse("bookings:booking_detail", kwargs={"booking_reference": booking.booking_reference}), {"action": "cancel", "owner_notes": "Vehicle needed", "cancellation_reason": "Maintenance"})
        booking.refresh_from_db()
        self.vehicle.refresh_from_db()
        self.assertEqual(booking.booking_status, Booking.Status.CANCELLED)
        self.assertEqual(self.vehicle.availability_status, Vehicle.AvailabilityStatus.AVAILABLE)

    def test_owner_and_renter_permissions_and_renter_cancellation(self):
        booking = self.create_booking()
        self.client.force_login(self.other_owner)
        self.assertEqual(self.client.get(reverse("bookings:booking_detail", kwargs={"booking_reference": booking.booking_reference})).status_code, 404)
        self.client.force_login(self.renter)
        response = self.client.post(reverse("bookings:booking_detail", kwargs={"booking_reference": booking.booking_reference}), {"cancellation_reason": "Plans changed"})
        self.assertRedirects(response, reverse("bookings:booking_detail", kwargs={"booking_reference": booking.booking_reference}))
        booking.refresh_from_db()
        self.assertEqual(booking.booking_status, Booking.Status.CANCELLED)
        self.client.force_login(self.second_renter)
        self.assertEqual(self.client.get(reverse("bookings:booking_detail", kwargs={"booking_reference": booking.booking_reference})).status_code, 404)

    def test_owner_can_reject_pending_booking_and_member_cannot_manage_owner_requests(self):
        booking = self.create_booking()
        self.client.force_login(self.renter)
        self.assertEqual(self.client.get(reverse("bookings:manage")).status_code, 403)
        self.client.force_login(self.owner)
        self.client.post(reverse("bookings:booking_detail", kwargs={"booking_reference": booking.booking_reference}), {"action": "reject", "owner_notes": "Unavailable for those dates"})
        booking.refresh_from_db()
        self.assertEqual(booking.booking_status, Booking.Status.REJECTED)
