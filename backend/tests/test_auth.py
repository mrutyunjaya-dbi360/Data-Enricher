from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from accounts.models import Tenant, User
from django.utils import timezone


@override_settings(USE_SQLITE=True)
class AuthTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(name="T", slug="t")
        self.user = User.objects.create_user(
            email="u@example.com", password="pass12345",
            tenant=self.tenant, role="member", status="active",
            email_verified_at=timezone.now(),
        )
        self.admin = User.objects.create_user(
            email="a@example.com", password="pass12345",
            tenant=self.tenant, role="admin", status="active",
            email_verified_at=timezone.now(), is_staff=True,
        )

    def test_login(self):
        r = self.client.post("/api/auth/login", {"email": "u@example.com", "password": "pass12345"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertIn("access", r.data)

    def test_deactivated_blocked(self):
        self.user.status = "deactivated"
        self.user.save()
        r = self.client.post("/api/auth/login", {"email": "u@example.com", "password": "pass12345"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_me(self):
        r = self.client.post("/api/auth/login", {"email": "u@example.com", "password": "pass12345"}, format="json")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        m = self.client.get("/api/auth/me")
        self.assertEqual(m.status_code, 200)
        self.assertEqual(m.data["email"], "u@example.com")
