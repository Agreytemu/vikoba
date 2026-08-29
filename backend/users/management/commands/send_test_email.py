from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Send a plain test email through the configured mail backend. "
        "Use this on Render to verify SMTP (Gmail app password) works: "
        "python manage.py send_test_email --to you@example.com"
    )

    def add_arguments(self, parser):
        parser.add_argument("--to", dest="to", required=True, help="Recipient email address")

    def handle(self, *args, **options):
        recipient = options["to"].strip()
        subject = f"[{settings.SYSTEM_NAME}] SMTP test"
        body = (
            "This is a test email from Vikoba Kidigitali.\n\n"
            "If you can read this, SMTP is configured correctly.\n"
        )

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"Mail backend: {settings.EMAIL_BACKEND} "
                f"(host={getattr(settings, 'EMAIL_HOST', '-')}, "
                f"port={getattr(settings, 'EMAIL_PORT', '-')}, "
                f"from={settings.DEFAULT_FROM_EMAIL})"
            )
        )

        try:
            send_mail(
                subject,
                body,
                settings.DEFAULT_FROM_EMAIL,
                [recipient],
                fail_silently=False,
            )
        except Exception as exc:  # noqa: BLE001 - surface the SMTP error verbatim
            raise CommandError(f"Email failed: {type(exc).__name__}: {exc}")

        self.stdout.write(self.style.SUCCESS(f"Test email delivered to {recipient}"))
        self.stdout.write(
            "If this worked, EMAIL_HOST_USER/EMAIL_HOST_PASSWORD are correct. "
            "If it failed, check the credential error above (Gmail needs the "
            "16-character App Password, not your normal password, with "
            "2-Step Verification enabled)."
        )