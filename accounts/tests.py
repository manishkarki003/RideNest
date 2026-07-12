from io import BytesIO

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import MemberVerification, User


def image_upload(name):
    image = Image.new("RGB", (10, 10), color="white")
    content = BytesIO()
    image.save(content, format="PNG")
    return SimpleUploadedFile(name, content.getvalue(), content_type="image/png")


class AccountTestCase(TestCase):
    password = "SafePassword123!"

    def create_user(self, username="asha", email="asha@example.com"):
        return get_user_model().objects.create_user(
            username=username,
            email=email,
            full_name="Asha Karki",
            password=self.password,
        )


class RegistrationTests(AccountTestCase):
    def test_member_can_register_and_is_logged_in(self):
        response = self.client.post(reverse("accounts:register"), {
            "full_name": "Asha Karki",
            "username": "asha",
            "email": "asha@example.com",
            "phone_number": "+977 9800000000",
            "address": "Kathmandu",
            "password1": self.password,
            "password2": self.password,
        })
        self.assertRedirects(response, reverse("core:home"))
        user = User.objects.get(username="asha")
        self.assertEqual(user.role, User.Role.MEMBER)
        self.assertEqual(self.client.session["_auth_user_id"], str(user.pk))

    def test_registration_rejects_duplicate_email(self):
        self.create_user()
        response = self.client.post(reverse("accounts:register"), {
            "full_name": "Another Asha", "username": "another", "email": "ASHA@example.com",
            "password1": self.password, "password2": self.password,
        })
        self.assertContains(response, "already exists")
        self.assertEqual(User.objects.count(), 1)


class LoginLogoutTests(AccountTestCase):
    def setUp(self):
        self.user = self.create_user()

    def test_user_can_log_in_with_email_and_remember_session(self):
        response = self.client.post(reverse("accounts:login"), {
            "username": self.user.email, "password": self.password, "remember_me": "on",
        })
        self.assertRedirects(response, reverse("core:home"))
        self.assertEqual(self.client.session["_auth_user_id"], str(self.user.pk))
        self.assertNotEqual(self.client.session.get_expiry_age(), 0)

    def test_logout_requires_post_and_clears_session(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(response, reverse("core:home"))
        self.assertNotIn("_auth_user_id", self.client.session)


class ProfileTests(AccountTestCase):
    def setUp(self):
        self.user = self.create_user()
        self.client.force_login(self.user)

    def test_profile_update_changes_only_permitted_fields(self):
        response = self.client.post(reverse("accounts:profile_edit"), {
            "full_name": "Asha Shrestha", "email": "new@example.com", "phone_number": "+977 9811111111",
            "address": "Lalitpur", "role": User.Role.ADMIN, "is_verified": "on",
        })
        self.assertRedirects(response, reverse("accounts:profile"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.full_name, "Asha Shrestha")
        self.assertEqual(self.user.role, User.Role.MEMBER)
        self.assertFalse(self.user.is_verified)

    def test_profile_requires_authentication(self):
        self.client.logout()
        response = self.client.get(reverse("accounts:profile"))
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={reverse('accounts:profile')}")


class PasswordManagementTests(AccountTestCase):
    def setUp(self):
        self.user = self.create_user()
        self.client.force_login(self.user)

    def test_user_can_change_password(self):
        response = self.client.post(reverse("accounts:password_change"), {
            "old_password": self.password,
            "new_password1": "AnotherSafePassword123!",
            "new_password2": "AnotherSafePassword123!",
        })
        self.assertRedirects(response, reverse("accounts:password_change_done"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("AnotherSafePassword123!"))


class VerificationTests(AccountTestCase):
    def setUp(self):
        self.user = self.create_user()
        self.client.force_login(self.user)

    def test_user_can_submit_member_verification(self):
        document = image_upload("citizenship.png")
        response = self.client.post(reverse("accounts:verification"), {
            "document_type": MemberVerification.DocumentType.CITIZENSHIP,
            "document_number": "12-34-56-78901",
            "document_image": document,
        })
        self.assertRedirects(response, reverse("accounts:profile"))
        submission = MemberVerification.objects.get(user=self.user)
        self.assertEqual(submission.status, MemberVerification.Status.PENDING)
        self.assertNotEqual(submission.document_image.name, "citizenship.png")

    def test_pending_verification_cannot_be_submitted_twice(self):
        MemberVerification.objects.create(
            user=self.user,
            document_type=MemberVerification.DocumentType.PASSPORT,
            document_number="P1234567",
            document_image=image_upload("passport.png"),
        )
        response = self.client.post(reverse("accounts:verification"), {})
        self.assertRedirects(response, reverse("accounts:profile"))
        self.assertEqual(MemberVerification.objects.filter(user=self.user).count(), 1)
