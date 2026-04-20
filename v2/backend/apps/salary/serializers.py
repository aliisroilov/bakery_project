from rest_framework import serializers

from .models import SalaryPayment, SalaryRate


class SalaryRateSerializer(serializers.ModelSerializer):
    user_display = serializers.CharField(source="user.display_name", read_only=True)

    class Meta:
        model = SalaryRate
        fields = [
            "id", "user", "user_display",
            "rate_type", "currency", "rate",
            "initial_balance", "note",
            "created_at",
        ]
        read_only_fields = ["created_at"]


class SalaryPaymentSerializer(serializers.ModelSerializer):
    user_display = serializers.CharField(source="user.display_name", read_only=True)
    account_name = serializers.CharField(source="account.name", read_only=True)
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)

    class Meta:
        model = SalaryPayment
        fields = [
            "id", "user", "user_display",
            "kind", "kind_display",
            "currency", "amount",
            "account", "account_name",
            "occurred_at", "note",
            "period_start", "period_end",
            "created_by", "created_at",
        ]
        read_only_fields = ["created_at"]
