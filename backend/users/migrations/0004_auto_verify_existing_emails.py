"""Data migration: mark existing accounts as email-verified.

When email verification was introduced, all previously registered users never
went through the 6-digit code flow. Marking them verified keeps staff and any
pre-existing members from being locked out of their accounts.
"""

from django.db import migrations


def auto_verify_existing_users(apps, schema_editor):
    User = apps.get_model("users", "User")
    User.objects.filter(email_verified=False).update(email_verified=True)


def reverse(apps, schema_editor):
    # Nothing to restore: the flag default is False so rows would be False again
    # only if we reset them, which would lock everyone out.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0003_user_email_verified_emailverificationcode"),
    ]

    operations = [
        migrations.RunPython(auto_verify_existing_users, reverse),
    ]