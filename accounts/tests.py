from django.test import TestCase
from django.urls import reverse
from .models import User


class AuthenticationTests(TestCase):
    def test_member_can_register_and_is_logged_in(self):
        response = self.client.post(reverse("accounts:register"), {
            "full_name": "Asha Karki",
            "username": "asha",
            "email": "asha@example.com",
            "phone_number": "+977 9800000000",
            "address": "Kathmandu",
            "role": User.Role.MEMBER,
            "password1": "SafePassword123!",
            "password2": "SafePassword123!",
        })
        self.assertRedirects(response, reverse("core:home"))
        user = User.objects.get(username="asha")
        self.assertEqual(user.full_name, "Asha Karki")
        self.assertEqual(user.role, User.Role.MEMBER)
        self.assertTrue(user.is_authenticated)

    def test_public_registration_cannot_create_admin(self):
        response = self.client.post(reverse("accounts:register"), {
            "full_name": "Admin Attempt",
            "username": "attempt",
            "email": "attempt@example.com",
            "role": User.Role.ADMIN,
            "password1": "SafePassword123!",
            "password2": "SafePassword123!",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="attempt").exists())
