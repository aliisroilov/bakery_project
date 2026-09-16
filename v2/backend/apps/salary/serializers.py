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
        read_only_fields = ["created_at"]

    def validate(self, attrs):
        """Keep one rate per (user, product) — re-saving an existing pair updates
        it instead of 500ing on the unique constraint."""
        user = attrs.get("user") or getattr(self.instance, "user", None)
        product = attrs.get("product") or getattr(self.instance, "product", None)
        if user and product:
            clash = UserProductRate.objects.filter(user=user, product=product)
            if self.instance:
                clash = clash.exclude(pk=self.instance.pk)
            if clash.exists():
                raise serializers.ValidationError(
                    {"product": "Bu ishchi uchun bu mahsulot tarifi allaqachon mavjud."}
                )
        return attrs


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
