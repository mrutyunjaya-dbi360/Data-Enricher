from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import Tenant, User


class Command(BaseCommand):
    help = "Seed default tenant and optional admin user"

    def add_arguments(self, parser):
        parser.add_argument("--email", default="admin@scrapeops.local")
        parser.add_argument("--password", default="admin12345")
        parser.add_argument("--name", default="Admin")

    def handle(self, *args, **opts):
        tenant, created = Tenant.objects.get_or_create(
            slug="default",
            defaults={"name": "Default", "domain_allowlist": []},
        )
        self.stdout.write(f"Tenant: {tenant.slug} ({'created' if created else 'exists'})")
        email = opts["email"].lower()
        user, uc = User.objects.get_or_create(
            email=email,
            defaults={
                "full_name": opts["name"],
                "role": "admin",
                "status": "active",
                "tenant": tenant,
                "email_verified_at": timezone.now(),
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if uc:
            user.set_password(opts["password"])
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Admin created: {email} / {opts['password']}"))
        else:
            if not user.tenant_id:
                user.tenant = tenant
                user.save()
            self.stdout.write(f"Admin exists: {email}")
