"""Global constants for bakery v2."""


class Currency:
    """Currency codes. UZS and USD are tracked separately — never summed."""

    UZS = "UZS"
    USD = "USD"

    CHOICES = [
        (UZS, "UZS (so'm)"),
        (USD, "USD (dollar)"),
    ]


class MeshokBatch:
    """How many units equal one 'meshok' (batch) for production costing."""

    SIZE = 160


# Money fields use 2 decimal places for USD, but UZS is usually whole — 2dp is safe for both.
MONEY_MAX_DIGITS = 16
MONEY_DECIMAL_PLACES = 2

# Quantity fields (ingredients, production) use 3 decimal places.
QTY_MAX_DIGITS = 14
QTY_DECIMAL_PLACES = 3
