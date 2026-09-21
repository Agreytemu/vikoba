from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import (
    MembershipPlan,
    SavingsAccount,
    SavingsTransaction,
)
from community.models import Announcement, Meeting
from groups.models import GroupMembership, VikobaGroup
from loans.models import LoanApplication, LoanProduct
from members.models import Member
from users.models import User


class Command(BaseCommand):
    help = "Seed a demo member login with portal mock data (local dev only)"

    def handle(self, *args, **options):
        if not settings.DEBUG and (
            settings.DATABASE_MODE != "sqlite" or getattr(settings, "DATABASE_URL", None)
        ):
            raise CommandError("seed_member_demo is disabled outside local development.")

        now = timezone.now()
        admin = User.objects.filter(email="admin@example.com").first()

        # ---------- 1. Demo login (email login) ----------
        demo, created = User.objects.get_or_create(
            email="demo@vikoba.local",
            defaults={"username": "demo", "role": "ME", "email_verified": True},
        )
        demo.username = "demo"
        demo.role = "ME"
        demo.email_verified = True
        demo.is_active = True
        demo.set_password("Demo@2026")
        demo.save()
        self.stdout.write(f"Demo user: demo@vikoba.local / Demo@2026 ({'created' if created else 'updated'})")

        # ---------- 2. Demo member linked to that login ----------
        member = Member.objects.order_by("created_at").first()
        if member is None:
            member = Member.objects.create(
                first_name="Juma",
                last_name="Mwansa",
                phone_number="+255712345678",
                email="demo@vikoba.local",
            )
        member.user = demo
        member.first_name = "Juma"
        member.last_name = "Mwansa"
        member.phone_number = "+255712345678"
        member.email = "demo@vikoba.local"
        member.date_of_birth = now.date().replace(year=now.year - 32)
        member.country = "Tanzania"
        member.permanent_address = "P.O. Box 123, Ilala"
        member.street = "Uhuru Street"
        member.region = "Dar es Salaam"
        member.citizenship_type = "BY_BIRTH"
        member.gender = "MALE"
        member.occupation = "Business owner"
        member.preferred_currency = "TZS"
        member.phone_verified = True
        member.verification_submitted = True
        member.is_verified = True
        member.is_onboarded = True
        member.onboarded_at = now
        member.status = "Active"
        member.save()

        # ---------- 3. Membership plans ----------
        # Plans are created here only for the demo; in production they are
        # managed by staff in the Django admin (accounts → membership plans).
        MembershipPlan.objects.update_or_create(
            name="Starter",
            defaults={
                "price": Decimal("20000"),
                "currency": "TZS",
                "interval": "monthly",
                "features": ["Up to 3 groups", "Contributions & loans", "Email support"],
                "is_active": True,
                "created_by": admin,
            },
        )
        growth, _ = MembershipPlan.objects.update_or_create(
            name="Growth",
            defaults={
                "price": Decimal("50000"),
                "currency": "TZS",
                "interval": "monthly",
                "features": ["Up to 10 groups", "Advanced reports", "Priority support", "WhatsApp alerts"],
                "is_active": True,
                "created_by": admin,
            },
        )
        MembershipPlan.objects.update_or_create(
            name="Premium",
            defaults={
                "price": Decimal("100000"),
                "currency": "TZS",
                "interval": "monthly",
                "features": ["Unlimited groups", "Dedicated support", "All reports & exports"],
                "is_active": True,
                "created_by": admin,
            },
        )
        member.selected_plan = growth
        member.save(update_fields=["selected_plan"])

        # ---------- 4. Groups + memberships ----------
        upendo, _ = VikobaGroup.objects.get_or_create(
            name="Upendo Group",
            defaults={
                "area": "Ilala",
                "region": "Dar es Salaam",
                "country": "Tanzania",
                "description": "Weekly savings and loans group.",
                "created_by": member,
                "status": "ACTIVE",
            },
        )
        amani, _ = VikobaGroup.objects.get_or_create(
            name="Amani Group",
            defaults={
                "area": "Nyakato",
                "region": "Mwanza",
                "country": "Tanzania",
                "description": "Community VICOBA group.",
                "created_by": member,
                "status": "ACTIVE",
            },
        )
        GroupMembership.objects.update_or_create(
            group=upendo,
            member=member,
            defaults={"role": "TREASURER", "shares_count": 45, "is_active": True},
        )
        GroupMembership.objects.update_or_create(
            group=amani,
            member=member,
            defaults={"role": "MEMBER", "shares_count": 20, "is_active": True},
        )

        # ---------- 5. Meetings (one upcoming Saturday 10:00) ----------
        days_until_sat = (5 - now.weekday()) % 7 or 7
        saturday = (now + timedelta(days=days_until_sat)).replace(
            hour=10, minute=0, second=0, microsecond=0
        )
        Meeting.objects.update_or_create(
            title="Weekly Contributions Meeting",
            defaults={
                "description": "Bring your weekly michango and hisa payments.",
                "starts_at": saturday,
                "ends_at": saturday + timedelta(hours=2),
                "location": "Ilala Community Hall",
                "created_by": admin,
            },
        )
        Meeting.objects.get_or_create(
            title="Share-Out Planning Session",
            defaults={
                "description": "Planning the end-of-cycle mgawo.",
                "starts_at": now - timedelta(days=9, hours=3),
                "ends_at": now - timedelta(days=9, hours=1),
                "location": "Ilala Community Hall",
                "created_by": admin,
            },
        )

        # ---------- 6. Announcement ----------
        Announcement.objects.get_or_create(
            title="Welcome to VICOBA kidigitali",
            defaults={
                "body": "Save weekly, buy hisa, and apply for loans right from your phone.",
                "status": "PUBLISHED",
                "pinned": True,
                "author": admin,
            },
        )

        # ---------- 7. Wallet transactions on the member's first account ----------
        account = SavingsAccount.objects.filter(member=member).order_by("opened_at").first()
        if account is not None and not SavingsTransaction.objects.filter(
            account=account, reference__startswith="DEMO-"
        ).exists():
            txns = [
                ("deposit", "20000.00", "Weekly michango", 12),
                ("deposit", "15000.00", "Hisa purchase", 9),
                ("deposit", "5000.00", "Social fund", 6),
                ("withdrawal", "8000.00", "School fees", 3),
                ("deposit", "10000.00", "Weekly michango", 1),
            ]
            for i, (kind, amount, narration, days_ago) in enumerate(txns, start=1):
                SavingsTransaction.objects.create(
                    account=account,
                    transaction_type=kind,
                    amount=Decimal(amount),
                    reference=f"DEMO-{i:04d}",
                    narration=narration,
                    performed_by=admin,
                    created_at=now - timedelta(days=days_ago),
                )
            account.balance = Decimal("1500.00") + Decimal("20000") + Decimal("15000") + Decimal(
                "5000"
            ) - Decimal("8000") + Decimal("10000")
            account.save(update_fields=["balance"])

        # ---------- 8. One submitted loan application ----------
        product = LoanProduct.objects.filter(is_active=True).first()
        if product is not None and not LoanApplication.objects.filter(member=member).exists():
            LoanApplication.objects.create(
                member=member,
                loan_type=product,
                requested_amount=Decimal("50000.00"),
                purpose="Expand small business",
                repayment_period_months=12,
                status="submitted",
                created_by=demo,
                submitted_by=demo,
                submitted_at=now - timedelta(days=2),
            )

        self.stdout.write(self.style.SUCCESS("Member portal demo data seeded."))
