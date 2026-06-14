"""User model + activity log + nonvoy staff profile."""
from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.core.models import ArchivableModel, TimestampedModel


class Role(models.TextChoices):
    """User roles. Admin is the Django superuser flag, not stored here."""

    MANAGER = "manager", "Manager"
    DRIVER = "driver", "Haydovchi"
    VIEWER = "viewer", "Ko'ruvchi"
    NONVOY = "nonvoy", "Nonvoy"
    ACCOUNTANT = "accountant", "Buxgalter"


class User(AbstractUser, ArchivableModel):
    """Custom user. We add role, phone, and archivable support."""

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.VIEWER)
    phone = models.CharField(max_length=32, blank=True)
    full_name = models.CharField(max_length=255, blank=True)
    produced_product = models.ForeignKey(
        "products.Product",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="producers",
        help_text="For nonvoy staff: which product this baker produces.",
    )
    # Snapshot of the user's positions (group memberships, assigned shops) taken
    # at archive time so "qaytarish" (restore) can put them back. Empty when active.
    archived_state = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-date_joined"]

    @property
    def display_name(self) -> str:
        return self.full_name or self.get_full_name() or self.username

    def __str__(self) -> str:
        return f"{self.display_name} ({self.get_role_display()})"


class NonvoyProfile(TimestampedModel):
    """Extra profile fields specific to baker (nonvoy) staff.

    Feature #8 — dedicated staff model for bakers.
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="nonvoy_profile",
        limit_choices_to={"role": Role.NONVOY},
    )
    passport = models.CharField(max_length=32, blank=True)
    address = models.TextField(blank=True)
    hired_date = models.DateField(null=True, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        verbose_name = "Nonvoy profile"
        verbose_name_plural = "Nonvoy profiles"

    def __str__(self) -> str:
        return f"Nonvoy: {self.user.display_name}"


class EmployeeGroup(TimestampedModel):
    """A named group of nonvoy (baker) employees — for group-based production attribution."""

    name = models.CharField(max_length=100, unique=True)
    members = models.ManyToManyField(
        User,
        blank=True,
        related_name="employee_groups",
        limit_choices_to={"role": Role.NONVOY},
    )
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class UserActivityLog(models.Model):
    """Every authenticated request — used for audit / activity logs page (#15)."""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="activity_logs"
    )
    path = models.CharField(max_length=500)
    method = models.CharField(max_length=10)
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["user", "-timestamp"]),
            models.Index(fields=["-timestamp"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.username} {self.method} {self.path} @ {self.timestamp:%Y-%m-%d %H:%M}"
