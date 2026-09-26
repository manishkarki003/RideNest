from io import BytesIO

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .forms import VehicleImageFormSet
from .models import Vehicle, VehicleImage


def image_upload(name: str = "vehicle.png") -> SimpleUploadedFile:
    image = Image.new("RGB", (20, 20), color="navy")
    content = BytesIO()
    image.save(content, format="PNG")
    return SimpleUploadedFile(name, content.getvalue(), content_type="image/png")


class VehicleTestCase(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="owner", email="owner@example.com", full_name="Vehicle Owner",
            password="SafePassword123!", role="owner",
        )
        self.other_owner = get_user_model().objects.create_user(
            username="other", email="other@example.com", full_name="Other Owner",
            password="SafePassword123!", role="owner",
        )
        self.member = get_user_model().objects.create_user(
            username="member", email="member@example.com", full_name="Member User",
            password="SafePassword123!",
        )

    def vehicle_data(self, **overrides):
        data = {
            "name": "Toyota Land Cruiser", "brand": "Toyota", "model": "Land Cruiser",
            "manufacturing_year": "2024", "vehicle_type": Vehicle.VehicleType.SUV,
            "fuel_type": Vehicle.FuelType.PETROL, "transmission": Vehicle.Transmission.AUTOMATIC,
            "seats": "7", "registration_number": "BA 1 PA 1234", "color": "White",
            "mileage": "12000", "engine_capacity": "3500", "rental_price_per_day": "12000.00",
            "security_deposit": "25000.00", "description": "Comfortable family SUV.",
            "pickup_address": "Kathmandu", "availability_status": Vehicle.AvailabilityStatus.AVAILABLE,
        }
        data.update(overrides)
        return data

    def create_vehicle(self, owner=None, **overrides):
        vehicle = Vehicle(owner=owner or self.owner, **self.vehicle_data(**overrides))
        vehicle.save()
        return vehicle

    def formset_data(self):
        return {"images-TOTAL_FORMS": "3", "images-INITIAL_FORMS": "0", "images-MIN_NUM_FORMS": "0", "images-MAX_NUM_FORMS": "1000"}


class VehicleCrudTests(VehicleTestCase):
    def test_owner_can_create_draft_vehicle(self):
        self.client.force_login(self.owner)
        data = self.vehicle_data()
        data["approval_status"] = Vehicle.ApprovalStatus.APPROVED
        data.update(self.formset_data())
        response = self.client.post(reverse("vehicles:add"), data)
        vehicle = Vehicle.objects.get(registration_number="BA 1 PA 1234")
        self.assertRedirects(response, reverse("vehicles:detail", kwargs={"slug": vehicle.slug}))
        self.assertEqual(vehicle.owner, self.owner)
        self.assertEqual(vehicle.approval_status, Vehicle.ApprovalStatus.DRAFT)

    def test_owner_can_edit_own_draft(self):
        vehicle = self.create_vehicle()
        self.client.force_login(self.owner)
        data = self.vehicle_data(name="Updated Land Cruiser", color="Black")
        data.update(self.formset_data())
        response = self.client.post(reverse("vehicles:edit", kwargs={"slug": vehicle.slug}), data)
        self.assertRedirects(response, reverse("vehicles:detail", kwargs={"slug": "updated-land-cruiser"}))
        vehicle.refresh_from_db()
        self.assertEqual(vehicle.color, "Black")
        self.assertEqual(vehicle.slug, "updated-land-cruiser")

    def test_other_owner_cannot_access_vehicle(self):
        vehicle = self.create_vehicle()
        self.client.force_login(self.other_owner)
        response = self.client.get(reverse("vehicles:detail", kwargs={"slug": vehicle.slug}))
        self.assertEqual(response.status_code, 404)

    def test_member_cannot_create_vehicle(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse("vehicles:add"))
        self.assertEqual(response.status_code, 403)

    def test_only_draft_vehicle_can_be_deleted(self):
        draft = self.create_vehicle()
        approved = self.create_vehicle(registration_number="BA 2 PA 9999", name="Approved Vehicle")
        approved.approval_status = Vehicle.ApprovalStatus.APPROVED
        approved.save(update_fields=["approval_status", "updated_at"])
        self.client.force_login(self.owner)
        response = self.client.post(reverse("vehicles:delete", kwargs={"slug": draft.slug}))
        self.assertRedirects(response, reverse("vehicles:mine"))
        self.assertFalse(Vehicle.objects.filter(pk=draft.pk).exists())
        response = self.client.post(reverse("vehicles:delete", kwargs={"slug": approved.slug}))
        self.assertRedirects(response, reverse("vehicles:detail", kwargs={"slug": approved.slug}))
        self.assertTrue(Vehicle.objects.filter(pk=approved.pk).exists())


class VehicleModelTests(VehicleTestCase):
    def test_slug_generation_is_unique_and_updates_only_when_name_changes(self):
        first = self.create_vehicle()
        second = self.create_vehicle(registration_number="BA 3 PA 1111")
        self.assertEqual(first.slug, "toyota-land-cruiser")
        self.assertEqual(second.slug, "toyota-land-cruiser-2")
        first.color = "Silver"
        first.save()
        self.assertEqual(first.slug, "toyota-land-cruiser")

    def test_image_validation_rejects_invalid_file(self):
        vehicle = self.create_vehicle()
        image = VehicleImage(vehicle=vehicle, image=SimpleUploadedFile("not-an-image.txt", b"invalid"))
        with self.assertRaises(ValidationError):
            image.full_clean()
        formset = VehicleImageFormSet(
            self.formset_data(),
            {"images-0-image": SimpleUploadedFile("pretend.png", b"not an image", content_type="image/png")},
            instance=vehicle,
            prefix="images",
        )
        self.assertFalse(formset.is_valid())

    def test_primary_image_falls_back_to_first_image(self):
        vehicle = self.create_vehicle()
        first = VehicleImage.objects.create(vehicle=vehicle, image=image_upload("first.png"))
        self.assertEqual(vehicle.primary_image, first)
        primary = VehicleImage.objects.create(vehicle=vehicle, image=image_upload("primary.png"), is_primary=True)
        self.assertEqual(vehicle.primary_image, primary)

    def test_approval_workflow_requires_reason_for_rejection_and_submission_needs_image(self):
        vehicle = self.create_vehicle()
        vehicle.approval_status = Vehicle.ApprovalStatus.REJECTED
        with self.assertRaises(ValidationError):
            vehicle.full_clean()
        vehicle.rejection_reason = "Please upload a clearer registration image."
        vehicle.full_clean()
        vehicle.approval_status = Vehicle.ApprovalStatus.DRAFT
        vehicle.rejection_reason = ""
        vehicle.save()
        self.client.force_login(self.owner)
        response = self.client.post(reverse("vehicles:submit", kwargs={"slug": vehicle.slug}))
        self.assertRedirects(response, reverse("vehicles:detail", kwargs={"slug": vehicle.slug}))
        vehicle.refresh_from_db()
        self.assertEqual(vehicle.approval_status, Vehicle.ApprovalStatus.DRAFT)
        VehicleImage.objects.create(vehicle=vehicle, image=image_upload())
        response = self.client.post(reverse("vehicles:submit", kwargs={"slug": vehicle.slug}))
        self.assertRedirects(response, reverse("vehicles:detail", kwargs={"slug": vehicle.slug}))
        vehicle.refresh_from_db()
        self.assertEqual(vehicle.approval_status, Vehicle.ApprovalStatus.PENDING)
        vehicle.approval_status = Vehicle.ApprovalStatus.APPROVED
        vehicle.full_clean()
        vehicle.save()
        self.assertEqual(vehicle.approval_status, Vehicle.ApprovalStatus.APPROVED)


class MarketplaceTests(VehicleTestCase):
    def create_public_vehicle(self, **overrides):
        vehicle = self.create_vehicle(**overrides)
        vehicle.approval_status = Vehicle.ApprovalStatus.APPROVED
        vehicle.is_active = True
        vehicle.availability_status = Vehicle.AvailabilityStatus.AVAILABLE
        vehicle.save(update_fields=["approval_status", "is_active", "availability_status", "updated_at"])
        return vehicle

    def test_marketplace_shows_only_publicly_visible_vehicles(self):
        visible = self.create_public_vehicle(name="Visible Vehicle")
        self.create_vehicle(name="Draft Vehicle", registration_number="BA 4 PA 1001")
        self.create_public_vehicle(name="Inactive Vehicle", registration_number="BA 4 PA 1002", is_active=False)
        Vehicle.objects.filter(name="Inactive Vehicle").update(is_active=False)
        self.create_public_vehicle(name="Rented Vehicle", registration_number="BA 4 PA 1003", availability_status=Vehicle.AvailabilityStatus.RENTED)
        Vehicle.objects.filter(name="Rented Vehicle").update(availability_status=Vehicle.AvailabilityStatus.RENTED)
        response = self.client.get(reverse("vehicles:marketplace"))
        self.assertContains(response, visible.name)
        self.assertNotContains(response, "Draft Vehicle")
        self.assertNotContains(response, "Inactive Vehicle")
        self.assertNotContains(response, "Rented Vehicle")

    def test_keyword_search_and_combined_filters(self):
        matching = self.create_public_vehicle(
            name="Electric City Ride", registration_number="BA 5 PA 1001", brand="Nissan", model="Leaf",
            vehicle_type=Vehicle.VehicleType.CAR, fuel_type=Vehicle.FuelType.ELECTRIC,
            transmission=Vehicle.Transmission.AUTOMATIC, seats=5, rental_price_per_day="4500.00",
            manufacturing_year=2023, description="Silent city commuter", pickup_address="Pokhara Lakeside",
        )
        self.create_public_vehicle(name="Petrol SUV", registration_number="BA 5 PA 1002", vehicle_type=Vehicle.VehicleType.SUV)
        response = self.client.get(reverse("vehicles:search"), {
            "q": "Lakeside", "vehicle_type": "car", "fuel_type": "electric", "transmission": "automatic",
            "seats": "5", "min_price": "4000", "max_price": "5000", "min_year": "2022",
            "max_year": "2024", "brand": "Nissan", "availability": "available",
        })
        self.assertContains(response, matching.name)
        self.assertNotContains(response, "Petrol SUV")

    def test_sorting_and_pagination_preserve_query_parameters(self):
        low = self.create_public_vehicle(name="Budget Car", registration_number="BA 6 PA 1000", rental_price_per_day="1000.00")
        self.create_public_vehicle(name="Premium Car", registration_number="BA 6 PA 1001", rental_price_per_day="9000.00")
        for number in range(1, 14):
            self.create_public_vehicle(name=f"Toyota {number}", registration_number=f"BA 8 PA {number}")
        response = self.client.get(reverse("vehicles:marketplace"), {"sort": "price_low", "brand": "Toyota"})
        self.assertEqual(response.context["page_obj"].paginator.per_page, 12)
        response = self.client.get(reverse("vehicles:marketplace"), {"sort": "price_low"})
        self.assertEqual(response.context["vehicles"][0], low)
        paged = self.client.get(reverse("vehicles:marketplace"), {"brand": "Toyota", "page": "2"})
        self.assertEqual(paged.context["page_obj"].number, 2)
        self.assertContains(paged, "brand=Toyota")

    def test_public_detail_is_protected_and_related_vehicles_exclude_current(self):
        self.owner.phone_number = "+977 9800000000"
        self.owner.save()
        current = self.create_public_vehicle(name="Toyota Corolla", registration_number="BA 7 PA 1001", brand="Toyota", vehicle_type=Vehicle.VehicleType.CAR)
        related = self.create_public_vehicle(name="Toyota Yaris", registration_number="BA 7 PA 1002", brand="Toyota", vehicle_type=Vehicle.VehicleType.CAR)
        unrelated = self.create_public_vehicle(name="Ford Ranger", registration_number="BA 7 PA 1003", brand="Ford", vehicle_type=Vehicle.VehicleType.PICKUP)
        response = self.client.get(reverse("vehicles:public_detail", kwargs={"slug": current.slug}))
        self.assertContains(response, related.name)
        self.assertNotContains(response, unrelated.name)
        self.assertNotContains(response, "+977 9800000000")
        self.assertContains(response, "application/ld+json")
        self.assertContains(response, "canonical")
        draft = self.create_vehicle(name="Private Draft", registration_number="BA 7 PA 1004")
        self.assertEqual(self.client.get(reverse("vehicles:public_detail", kwargs={"slug": draft.slug})).status_code, 404)
