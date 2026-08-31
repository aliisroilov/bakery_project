"""Money helpers. UZS + USD are tracked separately, NEVER summed together."""
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from .constants import Currency

ZERO = Decimal("0.00")
_QUANT = Decimal("0.01")


def quantize_money(value: Decimal | int | float | str) -> Decimal:
    """Round to 2 decimal places (ROUND_HALF_UP). Use for every money calculation."""
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(_QUANT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Money:
    """A pair of currency-separated amounts. Never summed across currencies."""

    uzs: Decimal = ZERO
    usd: Decimal = ZERO

    def __post_init__(self) -> None:
        object.__setattr__(self, "uzs", quantize_money(self.uzs))
        object.__setattr__(self, "usd", quantize_money(self.usd))

    def __add__(self, other: "Money") -> "Money":
        return Money(uzs=self.uzs + other.uzs, usd=self.usd + other.usd)

    def __sub__(self, other: "Money") -> "Money":
        return Money(uzs=self.uzs - other.uzs, usd=self.usd - other.usd)

    def is_zero(self) -> bool:
        return self.uzs == ZERO and self.usd == ZERO

    def as_dict(self) -> dict[str, str]:
        return {"uzs": str(self.uzs), "usd": str(self.usd)}

    @classmethod
    def uzs_only(cls, amount) -> "Money":
        return cls(uzs=quantize_money(amount), usd=ZERO)

    @classmethod
    def usd_only(cls, amount) -> "Money":
        return cls(uzs=ZERO, usd=quantize_money(amount))

    @classmethod
    def from_currency(cls, amount, currency: str) -> "Money":
        if currency == Currency.UZS:
            return cls.uzs_only(amount)
        if currency == Currency.USD:
            return cls.usd_only(amount)
        raise ValueError(f"Unknown currency: {currency}")


# ────────────────── USD → UZS conversion (reporting) ──────────────────
# Kassa balances stay per-currency and are NEVER summed. Reports are a different
# beast: the P&L waterfall is a single UZS statement, so a dollar expense has to
# be restated in UZS or it silently vanishes from Xarajatlar / Tan narxi / foyda.
# Every USD-capable expense row therefore carries the rate it was booked at
# (`exchange_rate`, UZS per 1 USD), mirroring Payment.exchange_rate.


def effective_rate(rate) -> Decimal:
    """UZS per 1 USD for a row, falling back to the standard rate.

    0 / None = legacy row recorded before the field existed — those are restated
    at DEFAULT_USD_RATE rather than dropped.
    """
    from .constants import DEFAULT_USD_RATE

    value = Decimal(str(rate)) if rate is not None else ZERO
    return value if value > 0 else Decimal(DEFAULT_USD_RATE)


def to_uzs(amount, currency: str, rate=None) -> Decimal:
    """Restate a (currency, amount) pair in UZS. UZS amounts pass through."""
    value = Decimal(str(amount)) if amount is not None else ZERO
    if currency != Currency.USD:
        return quantize_money(value)
    return quantize_money(value * effective_rate(rate))


def uzs_amount_expr(
    amount_field: str = "amount",
    rate_field: str = "exchange_rate",
    currency_field: str = "currency",
):
    """ORM expression form of `to_uzs` — for aggregating mixed-currency rows.

    Usage: qs.annotate(uzs=uzs_amount_expr()).aggregate(Sum("uzs"))
    """
    from django.db.models import Case, DecimalField, F, Value, When

    from .constants import DEFAULT_USD_RATE, MONEY_DECIMAL_PLACES

    output = DecimalField(max_digits=24, decimal_places=MONEY_DECIMAL_PLACES)
    return Case(
        When(
            **{currency_field: Currency.USD, f"{rate_field}__gt": 0},
            then=F(amount_field) * F(rate_field),
        ),
        When(
            **{currency_field: Currency.USD},
            then=F(amount_field) * Value(Decimal(DEFAULT_USD_RATE)),
        ),
        default=F(amount_field),
        output_field=output,
    )
