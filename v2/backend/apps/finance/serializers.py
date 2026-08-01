from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.core.constants import DEFAULT_USD_RATE, Currency

from .models import (
    CashHandover,
    ExpenseCategory,
    GeneralExpense,
    KassaAccount,
    KassaExchange,
    KassaTransaction,
    KassaTransfer,
    Payment,
)


class KassaAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = KassaAccount
        fields = [
            "id", "slug", "name", "description",
            "balance_uzs", "balance_usd",
            "created_at",
        ]
        read_only_fields = ["balance_uzs", "balance_usd", "created_at"]


class KassaTransactionSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source="account.name", read_only=True)
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)
    created_by_name = serializers.CharField(
        source="created_by.display_name", read_only=True, default=None
    )
    # The user's own comment on the source record (resolved in bulk by the
    # viewset). `note` is the auto-generated description; this is the real izoh.
    source_note = serializers.SerializerMethodField()

    class Meta:
        model = KassaTransaction
        fields = [
            "id", "account", "account_name",
            "kind", "kind_display", "currency", "amount",
            "reference_model", "reference_id",
            "note", "source_note", "occurred_at", "created_by", "created_by_name", "created_at",
        ]

    def get_source_note(self, obj):
        notes = self.context.get("source_notes") or {}
        return notes.get((obj.reference_model, obj.reference_id))
        read_only_fields = ["created_at"]


class PaymentSerializer(serializers.ModelSerializer):
    shop_name = serializers.CharField(source="shop.name", read_only=True)
    account_name = serializers.CharField(source="account.name", read_only=True)
    collected_by_name = serializers.CharField(
        source="collected_by.display_name", read_only=True, default=""
    )
    payment_type_display = serializers.CharField(
        source="get_payment_type_display", read_only=True
    )

    class Meta:
        model = Payment
        fields = [
            "id", "shop", "shop_name",
            "order", "order_date",
            "payment_type", "payment_type_display",
            "currency", "amount", "discount", "exchange_rate",
            "account", "account_name",
            "collected_by", "collected_by_name",
            "received_at", "note", "created_at",
        ]
        read_only_fields = ["created_at"]

    def validate(self, data):
        # Shops are invoiced in UZS, so a USD kirim needs a rate to settle their
        # debt. Fall back to the standard rate when the client didn't send one,
        # and never let a USD payment through with a zero/negative rate.
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


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = [
            "id", "name", "note", "is_archived",
            "include_in_pnl", "below_op_profit", "created_at",
        ]
        read_only_fields = ["created_at"]


class GeneralExpenseSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True, default="")
    account_name = serializers.CharField(source="account.name", read_only=True)

    class Meta:
        model = GeneralExpense
        fields = [
            "id", "category", "category_name", "title",
            "currency", "amount",
            "account", "account_name",
            "occurred_at", "note", "created_by", "created_at",
        ]
        read_only_fields = ["created_at"]


class KassaTransferSerializer(serializers.ModelSerializer):
    from_account_name = serializers.CharField(source="from_account.name", read_only=True)
    to_account_name = serializers.CharField(source="to_account.name", read_only=True)
    created_by_name = serializers.CharField(
        source="created_by.display_name", read_only=True, default=""
    )

    class Meta:
        model = KassaTransfer
        fields = [
            "id", "from_account", "from_account_name",
            "to_account", "to_account_name",
            "currency", "amount", "occurred_at", "note",
            "created_by", "created_by_name", "created_at",
        ]
        read_only_fields = ["created_at"]

    def validate(self, data):
        if data.get("from_account") == data.get("to_account"):
            raise serializers.ValidationError(
                {"to_account": "Bir xil kassaga o'tkazib bo'lmaydi."}
            )
        if data.get("amount", 0) <= 0:
            raise serializers.ValidationError(
                {"amount": "Summa musbat bo'lishi kerak."}
            )
        return data


class KassaExchangeSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source="account.name", read_only=True)
    created_by_name = serializers.CharField(
        source="created_by.display_name", read_only=True, default=""
    )

    class Meta:
        model = KassaExchange
        fields = [
            "id", "account", "account_name",
            "from_currency", "to_currency",
            "from_amount", "to_amount", "rate",
            "occurred_at", "note",
            "created_by", "created_by_name", "created_at",
        ]
        read_only_fields = ["created_at"]

    def validate(self, data):
        if data.get("from_currency") == data.get("to_currency"):
            raise serializers.ValidationError(
                {"to_currency": "Valyutalar har xil bo'lishi kerak."}
            )
        if data.get("from_amount", 0) <= 0 or data.get("to_amount", 0) <= 0:
            raise serializers.ValidationError(
                {"from_amount": "Summalar musbat bo'lishi kerak."}
            )
        return data


class CashHandoverSerializer(serializers.ModelSerializer):
    driver_name = serializers.CharField(source="driver.display_name", read_only=True)
    received_by_name = serializers.CharField(
        source="received_by.display_name", read_only=True, default=""
    )
    account_name = serializers.CharField(source="to_account.name", read_only=True)
    received_by = serializers.PrimaryKeyRelatedField(
        queryset=get_user_model().objects.all(),
        required=False,
    )

    class Meta:
        model = CashHandover
        fields = [
            "id", "driver", "driver_name",
            "received_by", "received_by_name",
            "to_account", "account_name",
            "currency", "amount", "occurred_at", "note",
            "created_at",
        ]
        read_only_fields = ["created_at"]
