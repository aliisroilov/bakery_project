from decimal import Decimal
from django.db import models, transaction
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.conf import settings


DECIMAL_KWARGS = dict(max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal('0'))])

class Unit(models.Model):
    """Measurement unit, e.g. kg, litr, dona"""
    name = models.CharField(max_length=50, unique=True)
    short = models.CharField(max_length=10, blank=True)

    class Meta:
        verbose_name = _("Unit")
        verbose_name_plural = _("Units")

    def __str__(self):
        return self.short or self.name


class Ingredient(models.Model):
    name = models.CharField(max_length=200, unique=True)
    quantity = models.DecimalField(**DECIMAL_KWARGS, default=Decimal('0'))
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name='ingredients')
    low_stock_threshold = models.DecimalField(
        **DECIMAL_KWARGS,
        default=Decimal('0'),
        help_text=_("Minimum quantity before alert (set by admin)")
    )

    class Meta:
        verbose_name = _("Ingredient")
        verbose_name_plural = _("Ingredients")

    def __str__(self):
        return f"{self.name} ({self.quantity} {self.unit})"

    @property
    def is_low_stock(self):
        """Returns True if quantity is below or equal to threshold."""
        if self.low_stock_threshold is None:
            return False
        return self.quantity <= self.low_stock_threshold


class Purchase(models.Model):
    """A purchase that increases ingredient stock"""
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE, related_name='purchases')
    quantity = models.DecimalField(**DECIMAL_KWARGS)
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True)

    class Meta:
        verbose_name = _("Purchase")
        verbose_name_plural = _("Purchases")
        ordering = ['-date']

    def __str__(self):
        return f"Purchase {self.ingredient} +{self.quantity} on {self.date.date()}"


class ProductRecipe(models.Model):
    """
    Recipe entry: how much of `ingredient` is needed to produce one meshok of `product`.
    This model is intentionally in inventory so you can edit recipes in Product admin
    (see instructions below).
    """
    # Use a lazy import of Product with a string app label to avoid circular import.
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='recipe_items')
    ingredient = models.ForeignKey(Ingredient, on_delete=models.PROTECT, related_name='used_in_recipes')
    amount_per_meshok = models.DecimalField(**DECIMAL_KWARGS)

    class Meta:
        verbose_name = _("Product recipe item")
        verbose_name_plural = _("Product recipe items")
        unique_together = ('product', 'ingredient')

    def __str__(self):
        return f"{self.ingredient.name}: {self.amount_per_meshok} per meshok of {self.product}"


class Production(models.Model):
    """Records a production event (produced N meshok of a Product). Stocks will be decreased automatically."""
    product = models.ForeignKey('products.Product', on_delete=models.PROTECT, related_name='productions')
    meshok = models.DecimalField(**DECIMAL_KWARGS)
    date = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True)

    class Meta:
        verbose_name = _("Production")
        verbose_name_plural = _("Productions")
        ordering = ['-date']

    def __str__(self):
        return f"{self.product} — {self.meshok} meshok on {self.date.date()}"

    def apply_consumption(self):
        """
        Deduct ingredients from inventory according to product's recipe and this meshok count.
        This creates ProductionIngredientUsage rows.
        """
        from django.apps import apps
        ProductionIngredientUsage = apps.get_model('inventory', 'ProductionIngredientUsage')
        # Get recipe items for product
        recipe_qs = self.product.recipe_items.select_related('ingredient').all()
        usages = []
        with transaction.atomic():
            for item in recipe_qs:
                total_needed = (item.amount_per_meshok * self.meshok).quantize(item.amount_per_meshok)
                ing = item.ingredient
                # If insufficient stock, you may choose to allow negative or raise. We'll allow negative but note it.
                ing.quantity = (ing.quantity - total_needed)
                ing.save(update_fields=['quantity'])
                usages.append(ProductionIngredientUsage(production=self, ingredient=ing, quantity_used=total_needed))
            # bulk create usages
            ProductionIngredientUsage.objects.bulk_create(usages)


class ProductionIngredientUsage(models.Model):
    """
    Records how much of an Ingredient was used for a particular Production.
    This allows reversing/adjusting when editing/deleting productions.
    """
    production = models.ForeignKey(Production, on_delete=models.CASCADE, related_name='ingredient_usages')
    ingredient = models.ForeignKey(Ingredient, on_delete=models.PROTECT)
    quantity_used = models.DecimalField(**DECIMAL_KWARGS)

    class Meta:
        verbose_name = _("Production ingredient usage")
        verbose_name_plural = _("Production ingredient usages")

    def __str__(self):
        return f"{self.production} used {self.quantity_used} {self.ingredient.unit} of {self.ingredient.name}"


class DailyBakeryProduction(models.Model):
    """
    Manager-entered daily production for finished bakery products.
    - quantity_produced: the total produced for this product on `date`.
    - date is editable so manager can correct previous days.
    - confirmed: when True, the record is locked from edits/deletes.
    Behavior:
      - creating: add quantity to BakeryProductStock
      - updating: compute delta and add to stock (delta may be negative)
      - deleting: remove previously-applied produced amount (i.e. subtract)
    """
    product = models.ForeignKey('products.Product', on_delete=models.PROTECT, related_name='daily_productions')
    quantity_produced = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0.000'))]
    )
    date = models.DateField(default=timezone.localdate)
    confirmed = models.BooleanField(default=False, help_text=_("When confirmed the daily production is locked."))
    note = models.TextField(blank=True)

    class Meta:
        verbose_name = _("Daily Bakery Production")
        verbose_name_plural = _("Daily Bakery Productions")
        ordering = ["-date"]
        unique_together = ("product", "date")  # one record per product per date

    def __str__(self):
        return f"{self.product.name} — {self.quantity_produced} (on {self.date})"

    def _get_stock(self):
        from inventory.models import BakeryProductStock
        stock, _ = BakeryProductStock.objects.get_or_create(
            product=self.product,
            defaults={"quantity": Decimal("0.000"), "pinned": True}
        )
        return stock

    def save(self, *args, **kwargs):
        from inventory.models import BakeryProductStock
        import logging
        logger = logging.getLogger(__name__)

        # If this is update: compute delta = new - old.
        creating = self._state.adding
        # If updating, fetch previous value in DB
        old_qty = None
        if not creating:
            try:
                old = DailyBakeryProduction.objects.get(pk=self.pk)
                old_qty = old.quantity_produced
                # If old was confirmed, prevent edits (unless you want an override)
                if old.confirmed and not self.confirmed:
                    # don't allow un-confirming via regular save
                    raise ValueError("Cannot edit a confirmed production record.")
            except DailyBakeryProduction.DoesNotExist:
                old_qty = None

        with transaction.atomic():
            super().save(*args, **kwargs)

            # Apply stock changes only on create or when quantity/date/product changed.
            # Use select_for_update to prevent race conditions
            stock, _ = BakeryProductStock.objects.select_for_update().get_or_create(
                product=self.product,
                defaults={"quantity": Decimal("0.000"), "pinned": True}
            )
            
            if creating:
                stock.quantity = stock.quantity + self.quantity_produced
                stock.save(update_fields=["quantity", "updated_at"])
                logger.info(
                    f"[PRODUCTION] Added {self.quantity_produced} to {self.product.name} stock. "
                    f"New stock: {stock.quantity}"
                )
            else:
                # If old_qty is None treat as create (shouldn't happen)
                if old_qty is None:
                    stock.quantity = stock.quantity + self.quantity_produced
                    stock.save(update_fields=["quantity", "updated_at"])
                else:
                    delta = (self.quantity_produced - old_qty)
                    if delta != Decimal("0"):
                        stock.quantity = stock.quantity + delta
                        stock.save(update_fields=["quantity", "updated_at"])
                        logger.info(
                            f"[PRODUCTION] Updated {self.product.name}: delta={delta}, "
                            f"new stock={stock.quantity}"
                        )

    def delete(self, *args, **kwargs):
        import logging
        logger = logging.getLogger(__name__)
        
        # Prevent deleting confirmed record
        if self.confirmed:
            raise ValueError("Cannot delete a confirmed production record.")

        # Remove the produced quantity from stock (reverse what save did)
        with transaction.atomic():
            from inventory.models import BakeryProductStock
            stock, _ = BakeryProductStock.objects.select_for_update().get_or_create(
                product=self.product,
                defaults={"quantity": Decimal("0.000"), "pinned": True}
            )
            stock.quantity = stock.quantity - self.quantity_produced
            stock.save(update_fields=["quantity", "updated_at"])
            
            logger.info(
                f"[PRODUCTION] Deleted production for {self.product.name}: "
                f"removed {self.quantity_produced}, new stock={stock.quantity}"
            )
            
            super().delete(*args, **kwargs)


class BakeryProductStock(models.Model):
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='bakery_stocks')
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    pinned = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.product.name} — {self.quantity}"
    


class InventoryRevisionReport(models.Model):
    """
    Logs manual adjustments to ingredient or bakery product stock.
    """
    ITEM_TYPE_CHOICES = [
        ('ingredient', 'Ingredient'),
        ('product', 'Bakery Product'),
    ]

    item_type = models.CharField(max_length=20, choices=ITEM_TYPE_CHOICES)
    ingredient = models.ForeignKey(Ingredient, null=True, blank=True, on_delete=models.CASCADE)
    product = models.ForeignKey('products.Product', null=True, blank=True, on_delete=models.CASCADE)
    old_quantity = models.DecimalField(max_digits=12, decimal_places=3)
    new_quantity = models.DecimalField(max_digits=12, decimal_places=3)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,  # <- dynamic reference to the actual user model
        on_delete=models.CASCADE
    )

    class Meta:
        verbose_name = "Inventory Revision Report"
        verbose_name_plural = "Inventory Revision Reports"
        ordering = ['-created_at']

    def __str__(self):
        target = self.ingredient or self.product
        return f"{target} revised: {self.old_quantity} → {self.new_quantity} by {self.user}"