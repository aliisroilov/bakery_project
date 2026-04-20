from rest_framework import serializers

from .models import (
    CashHandover,
    ExpenseCategory,
    GeneralExpense,
    KassaAccount,
    KassaTransaction,
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

    class Meta:
        model = KassaTransaction
        fields = [
            "id", "account", "account_name",
            "kind", "kind_display", "currency", "amount",
            "reference_model", "reference_id",
            "note", "occurred_at", "created_by", "created_at",
        ]
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
            "currency", "amount", "discount",
            "account", "account_name",
            "collected_by", "collected_by_name",
            "received_at", "note", "created_at",
        ]
        read_only_fields = ["created_at"]


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = ["id", "name", "note", "is_archived", "created_at"]
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


class CashHandoverSerializer(serializers.ModelSerializer):
    driver_name = serializers.CharField(source="driver.display_name", read_only=True)
    received_by_name = serializers.CharField(source="received_by.display_name", read_only=True)
    account_name = serializers.CharField(source="to_account.name", read_only=True)

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
