"""Products (Sutli, Chapchap, Marokash Patir, ...)."""
from django.db import models

from apps.core.constants import (
    MONEY_DECIMAL_PLACES,
    MONEY_MAX_DIGITS,
    QTY_DECIMAL_PLACES,
    QTY_MAX_DIGITS,
)
from apps.core.models import ArchivableModel, TimestampedModel


class Product(TimestampedModel, ArchivableModel):
    """Finished bakery product."""

    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)

    # Default sale price (UZS by default — shops can override via ShopProductPrice).
    default_price_uzs = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES, default=0
    )
    default_price_usd = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES, default=0
    )

    # Feature #14: production salary rate per single unit produced (per-product, in UZS).
    # Nonvoy earns this * produced_quantity.
    production_salary_per_unit_uzs = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES, default=0
    )

    # Communal (gas/electricity) and other misc costs, attributed per meshok (qop)
    # and folded into tan narxi (cost of goods) alongside materials and labour, so
    # the P&L gross profit reflects everything spent making the goods.
    communal_cost_per_meshok_uzs = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES, default=0,
        help_text="Kommunal (gaz/svet) — 1 qop (meshok) uchun, so'm. Tan narxiga qo'shiladi.",
    )
    other_cost_per_meshok_uzs = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES, default=0,
        help_text="Boshqa xarajat — 1 qop (meshok) uchun, so'm. Tan narxiga qo'shiladi.",
    )

    # Feature #24: cached cost price (tan narx) per unit — computed from recipe × ingredient prices.
    # Recomputed on ingredient purchase / recipe change via signal or nightly job.
    cost_price_uzs = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES, default=0
    )
    cost_price_updated_at = models.DateTimeField(null=True, blank=True)

    # "meshok size" — how many units equal one production batch.
    # Kept per-product in case different products use different batch sizes.
    meshok_size = models.DecimalField(
        max_digits=QTY_MAX_DIGITS, decimal_places=QTY_DECIMAL_PLACES, default=160
    )

    sort_order = models.IntegerField(default=0, db_index=True)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name
