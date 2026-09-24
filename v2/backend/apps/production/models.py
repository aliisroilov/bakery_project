"""
Production app — what gets baked, by whom, consuming what.

Feature #13: dashboard needs today/month production counts → use Production.
Feature #14: per-product production salary → Production tracks nonvoy + product.
Feature #21: per-nonvoy salary history (per-day qop count) → Production aggregation.
"""
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.constants import QTY_DECIMAL_PLACES, QTY_MAX_DIGITS
from apps.core.models import TimestampedModel


class Production(TimestampedModel):
    """
    One production run — a nonvoy, a group, or a hand-picked set of nonvoys
    produced N qop of a product.

    - Exactly ONE attribution is used: nonvoy OR group OR individuals.
    - unit_count is entered MANUALLY — actual yield varies (e.g. 160-165 per qop).
    - Stock is bumped by unit_count when the record is saved.
    """

    product = models.ForeignKey(
        "products.Product", on_delete=models.PROTECT, related_name="productions"
    )
    # Individual baker — nullable when a group is used.
    nonvoy = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="productions",
        limit_choices_to={"role": "nonvoy"},
        null=True,
        blank=True,
    )
    # Group of bakers — nullable when a single nonvoy is used.
    group = models.ForeignKey(
        "users.EmployeeGroup",
        on_delete=models.PROTECT,
        related_name="productions",
        null=True,
        blank=True,
    )
    # Ad-hoc crew — several bakers picked directly on the production form, without
    # having to pre-create a named EmployeeGroup first. Paid exactly like a group:
    # every selected worker earns their OWN tariff on the FULL qop/dona, never a
    # split share (see apps/salary/utils.py).
    individuals = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="ad_hoc_productions",
        limit_choices_to={"role": "nonvoy"},
    )
    # Quantity in "meshok" / qop (batch count).
    meshok_count = models.DecimalField(
        max_digits=QTY_MAX_DIGITS, decimal_places=QTY_DECIMAL_PLACES
    )
    # Total units actually produced — entered MANUALLY (not auto-calculated from meshok_size).
    unit_count = models.DecimalField(
        max_digits=QTY_MAX_DIGITS, decimal_places=QTY_DECIMAL_PLACES, default=0
    )
    occurred_at = models.DateTimeField(db_index=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["product", "-occurred_at"]),
            models.Index(fields=["nonvoy", "-occurred_at"]),
        ]
    def has_individuals(self) -> bool:
        """Whether an ad-hoc crew is attached.

        Django writes M2M rows only AFTER the instance is saved, so on an unsaved
        row the selection isn't queryable yet — a form can hand it over ahead of
        time via `_pending_individuals` (see ProductionAdminForm). The API path
        never needs this: the serializer validates the submitted list itself.
        """
        pending = getattr(self, "_pending_individuals", None)
        if pending is not None:
            return bool(pending)
        return bool(self.pk) and self.individuals.exists()

    def clean(self):
        # Exactly one attribution — otherwise a baker could be credited twice
        # (individually AND as a crew member) for the same batch.
        chosen = [bool(self.nonvoy_id), bool(self.group_id), self.has_individuals()]
        if sum(chosen) > 1:
            raise ValidationError(
                "Only one of nonvoy, group or individuals may be set."
            )
        if not any(chosen):
            raise ValidationError(
                "Either nonvoy, group or individuals must be set."
            )

    @property
    def actor_name(self) -> str:
        if self.nonvoy_id:
            return self.nonvoy.display_name
        if self.group_id:
            return self.group.name
        if self.pk:
            names = [u.display_name for u in self.individuals.all()]
            if names:
                return ", ".join(names)
        return "—"

    def __str__(self) -> str:
        return f"{self.product.name} · {self.meshok_count} qop · {self.actor_name}"


class ProductionIngredientUsage(models.Model):
    """Audit trail — which ingredients were consumed for a Production."""

    production = models.ForeignKey(
        Production, on_delete=models.CASCADE, related_name="ingredient_usages"
    )
    ingredient = models.ForeignKey(
        "inventory.Ingredient",
        on_delete=models.PROTECT,
        related_name="usages",
    )
    quantity_used = models.DecimalField(
        max_digits=QTY_MAX_DIGITS, decimal_places=QTY_DECIMAL_PLACES
    )
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recorded_at"]


class BakeryProductStock(TimestampedModel):
    """Finished goods inventory — quantity ready to deliver."""

    product = models.OneToOneField(
        "products.Product", on_delete=models.CASCADE, related_name="stock"
    )
    quantity = models.DecimalField(
        max_digits=QTY_MAX_DIGITS, decimal_places=QTY_DECIMAL_PLACES, default=0
    )
    pinned = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"{self.product.name}: {self.quantity}"


class InventoryRevisionReport(TimestampedModel):
    """Manual stock adjustment audit log (ingredient OR product)."""

    class ItemType(models.TextChoices):
        INGREDIENT = "ingredient", "Xomashyo"
        PRODUCT = "product", "Tayyor mahsulot"

    item_type = models.CharField(max_length=20, choices=ItemType.choices)
    ingredient = models.ForeignKey(
        "inventory.Ingredient",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="revisions",
    )
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="revisions",
    )
    old_quantity = models.DecimalField(
        max_digits=QTY_MAX_DIGITS, decimal_places=QTY_DECIMAL_PLACES
    )
    new_quantity = models.DecimalField(
        max_digits=QTY_MAX_DIGITS, decimal_places=QTY_DECIMAL_PLACES
    )
    note = models.TextField(blank=True)
    # Monetary value of the discrepancy at revision time (UZS):
    # (old_quantity − new_quantity) × ingredient avg_cost_uzs. Positive = shortage
    # (kamomad — a loss that ADDS to Tan narxi/COGS); negative = surplus (ortiqcha —
    # reduces COGS). Snapshotted on creation so later avg-cost drift can't distort
    # it. Null for product revisions and legacy rows. This is NOT a cash movement —
    # reviziya adjusts inventory value into cost of goods, never the kassa.
    value_uzs = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True
    )
    batch_id = models.UUIDField(null=True, blank=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="revisions_made",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        target = self.ingredient or self.product
        return f"{target} : {self.old_quantity} → {self.new_quantity}"
