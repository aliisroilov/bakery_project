"""Abstract base models shared across apps."""
from django.db import models


class TimestampedModel(models.Model):
    """Abstract base adding created_at / updated_at."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ArchivableModel(models.Model):
    """Abstract base for soft-archive pattern.

    Instead of deleting (which would cascade), we set is_archived=True.
    Active querysets filter is_archived=False; archived views show the rest.
    """

    is_archived = models.BooleanField(default=False, db_index=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    def archive(self) -> None:
        from django.utils import timezone

        self.is_archived = True
        self.archived_at = timezone.now()
        self.save(update_fields=["is_archived", "archived_at"])

    def unarchive(self) -> None:
        self.is_archived = False
        self.archived_at = None
        self.save(update_fields=["is_archived", "archived_at"])
