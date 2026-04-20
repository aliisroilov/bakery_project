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
