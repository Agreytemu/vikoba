import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Create the initial superuser from DJANGO_ADMIN_EMAIL / DJANGO_ADMIN_USERNAME / "
        "DJANGO_ADMIN_PASSWORD environment variables. Used to bootstrap the first admin "
        "on Render's free plan (no interactive Shell available). Idempotent and "
        "conservative: it never modifies an existing user and does nothing once any "
        "superuser exists."
    )

    def handle(self, *args, **options):
        User = get_user_model()
        email = os.environ.get("DJANGO_ADMIN_EMAIL", "").strip().lower()
        username = os.environ.get("DJANGO_ADMIN_USERNAME", "").strip()
        password = os.environ.get("DJANGO_ADMIN_PASSWORD", "").strip()

        if not email or not password:
            self.stdout.write(
                "ensure_admin: DJANGO_ADMIN_EMAIL/PASSWORD not set; nothing to do."
            )
            return

        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write(
                "ensure_admin: a superuser already exists; nothing to do."
            )
            return

        if not username:
            username = email.split("@")[0]

        User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
            role=User.ADMIN,
        )
        self.stdout.write(self.style.SUCCESS(f"ensure_admin: superuser created ({email})"))