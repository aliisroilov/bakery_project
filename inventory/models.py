from decimal import Decimal
from django.db import models, transaction
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator

# Use Decimal for quantities to support fractional meshok and fractional kg/litr etc.
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
    """Ingredient with current quantity and measurement unit"""
    name = models.CharField(max_length=200, unique=True)
    quantity = models.DecimalField(**DECIMAL_KWARGS, default=Decimal('0'))
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name='ingredients')

    class Meta:
        verbose_name = _("Ingredient")
        verbose_name_plural = _("Ingredients")

    def __str__(self):
        return f"{self.name} ({self.quantity} {self.unit})"


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
