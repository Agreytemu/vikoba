from django.db import models

from users.models import User


class Announcement(models.Model):
    """Staff-published notice visible to all members."""

    class Status(models.TextChoices):
        PUBLISHED = "PUBLISHED", "Published"
        DRAFT = "DRAFT", "Draft"
        ARCHIVED = "ARCHIVED", "Archived"

    title = models.CharField(max_length=200)
    body = models.TextField()
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    pinned = models.BooleanField(default=False)
    author = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="announcements",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-pinned", "-created_at"]

    def __str__(self):
        return self.title


class Meeting(models.Model):
    """Announced meeting / event for members."""

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    location = models.CharField(max_length=200, blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="meetings_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["starts_at"]

    def __str__(self):
        return self.title