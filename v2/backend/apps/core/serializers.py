from decimal import Decimal

from rest_framework import serializers  # noqa: F401

from .constants import DEFAULT_USD_RATE, Currency


class UsdRateMixin:
    """Normalises `exchange_rate` on any model with a (currency, exchange_rate) pair.

    Reports restate USD rows in UZS at this rate, so a USD row must never be
    stored without one — fall back to the standard rate when the client omits it.
    UZS rows are forced to 0 so a stale rate can't linger after a currency switch.
    """

    def validate(self, data):
        data = super().validate(data)
        currency = data.get(
            "currency", getattr(self.instance, "currency", Currency.UZS)
        )
        if currency == Currency.USD:
            rate = data.get(
                "exchange_rate", getattr(self.instance, "exchange_rate", None)
            )
            if not rate or rate <= 0:
                data["exchange_rate"] = Decimal(DEFAULT_USD_RATE)
        else:
            data["exchange_rate"] = Decimal(0)
        return data
