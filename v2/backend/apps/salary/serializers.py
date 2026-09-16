from rest_framework import serializers

from apps.core.serializers import UsdRateMixin

from .models import SalaryPayment, SalaryRate, UserProductRate


class SalaryRateSerializer(serializers.ModelSerializer):
    user_display = serializers.CharField(source="user.display_name", read_only=True)
    # Effective-dated rate history (read-only) so the UI can show/explain that a
    # rate change only applies forward and past periods keep their old rate.
    rate_periods = serializers.SerializerMethodField()

    class Meta:
        model = SalaryRate
        fields = [
            "id", "user", "user_display",
            "rate_type", "currency", "rate",
            "initial_balance", "reset_date", "week_start_day", "note",
            "rate_periods",
            "created_at",
        ]
        read_only_fields = ["created_at"]

    def get_rate_periods(self, obj):
        from .models import SalaryRatePeriod

        return [
            {
                "effective_from": p.effective_from.isoformat(),
                "rate": str(p.rate),
                "rate_type": p.rate_type,
                "currency": p.currency,
                "week_start_day": p.week_start_day,
            }
            for p in SalaryRatePeriod.objects.filter(user=obj.user).order_by("effective_from")
        ]


class UserProductRateSerializer(serializers.ModelSerializer):
    """One worker's pay rate for one product they are set up to produce."""

    user_display = serializers.CharField(source="user.display_name", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    # Batch size, so the UI can show the linked "1 dona" figure next to "1 qop"
    # without a second request (same paired-input idea as the product modal).
    meshok_size = serializers.DecimalField(
        source="product.meshok_size", max_digits=14, decimal_places=3, read_only=True
    )

    class Meta:
        model = UserProductRate
        fields = [
            "id", "user", "user_display",
            "product", "product_name", "meshok_size",
            "rate_per_meshok_uzs", "note",
            "created_at",
        ]
        # DRF derives a unique-together validator from the model constraint, so a
        # repeated (user, product) already comes back as a 400, not a 500.
        read_only_fields = ["created_at"]


class SalaryPaymentSerializer(UsdRateMixin, serializers.ModelSerializer):
    user_display = serializers.CharField(source="user.display_name", read_only=True)
    account_name = serializers.CharField(source="account.name", read_only=True)
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)

    class Meta:
        model = SalaryPayment
        fields = [
            "id", "user", "user_display",
            "kind", "kind_display",
            "currency", "amount", "exchange_rate",
            "account", "account_name",
            "occurred_at", "note",
            "period_start", "period_end",
            "created_by", "created_at",
        ]
        read_only_fields = ["created_at"]
