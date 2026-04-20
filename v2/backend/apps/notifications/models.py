"""In-app notifications. Feature #5 (loan-limit), Feature #10 (low-stock)."""
from django.conf import settings
from django.db import models


class NotificationKind(models.TextChoices):
    LOW_STOCK = "low_stock", "Xomashyo kam qoldi"
    SHOP_LIMIT_EXCEEDED = "shop_limit_exceeded", "Do'kon limitidan oshdi"
    ORDER_PRIORITY = "order_priority", "Shoshilinch buyurtma"
    CASH_HANDOVER = "cash_handover", "Pul topshirildi"
    GENERAL = "general", "Umumiy"


class NotificationSeverity(models.TextChoices):
    INFO = "info", "Info"
    WARNING = "warning", "Warning"
    CRITICAL = "critical", "Critical"


class Notification(models.Model):
    """One notification targeted at a specific user (or broadcast with user=null)."""

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
        help_text="Null = broadcast to all managers.",
    )
    kind = models.CharField(max_length=32, choices=NotificationKind.choices)
    severity = models.CharField(
        max_length=16, choices=NotificationSeverity.choices, default=NotificationSeverity.INFO
    )
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    # Loose reference to the triggering record.
    reference_model = models.CharField(max_length=64, blank=True)
    reference_id = models.PositiveIntegerField(null=True, blank=True)

    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read", "-created_at"]),
        ]

    def mark_read(self):
        from django.utils import timezone

        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=["is_read", "read_at"])

    def __str__(self) -> str:
        return f"[{self.get_kind_display()}] {self.title}"
