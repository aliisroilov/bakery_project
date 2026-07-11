from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F, Sum
from django.db.models.functions import TruncDate
from rest_framework import filters, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import ReadOrManagerWrite
from apps.finance.models import KassaAccount, KassaTransaction, KassaTransactionType
from apps.production.models import Production

from .models import PaymentKind, SalaryPayment, SalaryRate
from .serializers import SalaryPaymentSerializer, SalaryRateSerializer
from .utils import calculate_earned_period


class SalaryRateViewSet(viewsets.ModelViewSet):
    permission_classes = [ReadOrManagerWrite]
    serializer_class = SalaryRateSerializer
    queryset = SalaryRate.objects.select_related("user")

    def get_queryset(self):
        qs = super().get_queryset()
        if user := self.request.query_params.get("user"):
            qs = qs.filter(user_id=user)
        return qs


KIND_TO_KASSA_KIND = {
    "salary": KassaTransactionType.SALARY,
    "advance": KassaTransactionType.ADVANCE,
    "bonus": KassaTransactionType.BONUS,
    "deduction": KassaTransactionType.ADJUSTMENT,  # negative adjustment
}


class SalaryPaymentViewSet(viewsets.ModelViewSet):
    permission_classes = [ReadOrManagerWrite]
    serializer_class = SalaryPaymentSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["occurred_at", "amount"]

    def get_queryset(self):
        qs = SalaryPayment.objects.select_related("user", "account", "created_by")
        p = self.request.query_params
        if user := p.get("user"):
            qs = qs.filter(user_id=user)
        if kind := p.get("kind"):
            qs = qs.filter(kind=kind)
        if date_from := p.get("date_from"):
            qs = qs.filter(occurred_at__date__gte=date_from)
        if date_to := p.get("date_to"):
            qs = qs.filter(occurred_at__date__lte=date_to)
        return qs

    def perform_create(self, serializer):
        with transaction.atomic():
            payment = serializer.save(created_by=self.request.user)
            account = KassaAccount.objects.select_for_update().get(pk=payment.account_id)
            sign = -1 if payment.kind != "deduction" else 1  # paying out is negative for kassa
            delta = payment.amount * sign
            if payment.currency == "UZS":
                account.balance_uzs = F("balance_uzs") + delta
            else:
                account.balance_usd = F("balance_usd") + delta
            account.save(update_fields=["balance_uzs", "balance_usd"])
            KassaTransaction.objects.create(
                account=payment.account,
                kind=KIND_TO_KASSA_KIND.get(payment.kind, KassaTransactionType.SALARY),
                currency=payment.currency,
                amount=delta,
                reference_model="salary.SalaryPayment",
                reference_id=payment.id,
                note=f"{payment.get_kind_display()} · {payment.user.display_name}",
                occurred_at=payment.occurred_at,
                created_by=self.request.user,
            )

    def perform_update(self, serializer):
        with transaction.atomic():
            old = serializer.instance
            old_sign = -1 if old.kind != "deduction" else 1
            old_delta = old.amount * old_sign
            old_currency = old.currency
            old_account_id = old.account_id

            payment = serializer.save()

            new_sign = -1 if payment.kind != "deduction" else 1
            new_delta = payment.amount * new_sign

            # Reverse old transaction from old account.
            old_account = KassaAccount.objects.select_for_update().get(pk=old_account_id)
            if old_currency == "UZS":
                old_account.balance_uzs = F("balance_uzs") - old_delta
            else:
                old_account.balance_usd = F("balance_usd") - old_delta
            old_account.save(update_fields=["balance_uzs", "balance_usd"])

            # Apply new transaction to (possibly new) account.
            new_account = KassaAccount.objects.select_for_update().get(pk=payment.account_id)
            if payment.currency == "UZS":
                new_account.balance_uzs = F("balance_uzs") + new_delta
            else:
                new_account.balance_usd = F("balance_usd") + new_delta
            new_account.save(update_fields=["balance_uzs", "balance_usd"])

            # Update the linked KassaTransaction record if it exists.
            KassaTransaction.objects.filter(
                reference_model="salary.SalaryPayment",
                reference_id=payment.id,
            ).update(
                account=payment.account,
                kind=KIND_TO_KASSA_KIND.get(payment.kind, KassaTransactionType.SALARY),
                currency=payment.currency,
                amount=new_delta,
                occurred_at=payment.occurred_at,
                note=f"{payment.get_kind_display()} · {payment.user.display_name}",
            )

    def perform_destroy(self, instance):
        with transaction.atomic():
            sign = -1 if instance.kind != "deduction" else 1
            delta = instance.amount * sign
            account = KassaAccount.objects.select_for_update().get(pk=instance.account_id)
            # Reverse the original deduction from kassa.
            if instance.currency == "UZS":
                account.balance_uzs = F("balance_uzs") - delta
            else:
                account.balance_usd = F("balance_usd") - delta
            account.save(update_fields=["balance_uzs", "balance_usd"])
            KassaTransaction.objects.filter(
                reference_model="salary.SalaryPayment",
                reference_id=instance.id,
            ).delete()
            instance.delete()


class ProductionBreakdownView(APIView):
    """Feature #21: per-day qop breakdown for a nonvoy employee.

    Returns productions grouped by date (and product within each date) so the
    salary history drawer can show *why* a per-qop/per-product salary is what it is.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_id = request.query_params.get("user")
        if not user_id:
            return Response({"results": [], "count": 0})

        # Respect the salary reset date so the breakdown matches the earned figure
        # (production before the reset isn't counted toward salary).
        rate = SalaryRate.objects.filter(user_id=user_id).first()
        reset = rate.reset_date if rate else None

        # Both individual and group productions count the FULL quantity for this
        # user — matching the salary calculation (no split among group members).
        individual = Production.objects.filter(nonvoy_id=user_id).select_related("product")
        group_qs = Production.objects.filter(
            group__members__id=user_id, nonvoy__isnull=True
        ).select_related("product", "group")
        if reset:
            individual = individual.filter(occurred_at__date__gte=reset)
            group_qs = group_qs.filter(occurred_at__date__gte=reset)
        individual = list(individual.order_by("-occurred_at"))
        group_prods = list(group_qs.order_by("-occurred_at"))

        rows = [p for p in individual] + [p for p in group_prods]

        by_date: dict[str, dict] = {}
        for p in rows:
            d = p.occurred_at.date().isoformat()
            entry = by_date.setdefault(
                d,
                {
                    "date": d,
                    "total_meshok": Decimal("0"),
                    "total_units": Decimal("0"),
                    "products": {},
                },
            )
            meshok = Decimal(p.meshok_count or 0)
            units = Decimal(p.unit_count or 0)
            entry["total_meshok"] += meshok
            entry["total_units"] += units
            prod_entry = entry["products"].setdefault(
                p.product_id,
                {
                    "product_id": p.product_id,
                    "product_name": p.product.name,
                    "meshok": Decimal("0"),
                    "units": Decimal("0"),
                    "salary_per_unit": str(p.product.production_salary_per_unit_uzs or 0),
                },
            )
            prod_entry["meshok"] += meshok
            prod_entry["units"] += units

        results = []
        for d in sorted(by_date.keys(), reverse=True):
            entry = by_date[d]
            results.append(
                {
                    "date": entry["date"],
                    "total_meshok": str(entry["total_meshok"]),
                    "total_units": str(entry["total_units"]),
                    "products": [
                        {
                            "product_id": pv["product_id"],
                            "product_name": pv["product_name"],
                            "meshok": str(pv["meshok"]),
                            "units": str(pv["units"]),
                            "salary_per_unit": pv["salary_per_unit"],
                        }
                        for pv in entry["products"].values()
                    ],
                }
            )

        return Response({"results": results, "count": len(results)})


class SalaryEmployeeSummaryView(APIView):
    """Per-employee dashboard: rate config, earned/paid/remaining, last payment.

    Returns staff that can have salary (nonvoy + driver + accountant + manager).
    Viewer role excluded. Archived users excluded.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        User = get_user_model()
        payable_roles = ["nonvoy", "driver", "accountant", "manager"]
        role_filter = request.query_params.get("role")
        roles = [role_filter] if role_filter in payable_roles else payable_roles

        users = (
            User.objects.filter(role__in=roles, is_archived=False)
            .select_related("salary_rate", "produced_product")
            .order_by("role", "username")
        )

        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")

        results = []
        for u in users:
            rate_obj = getattr(u, "salary_rate", None)
            # Per-period model — each month/range stands alone. Everything below
            # is scoped to [date_from, date_to]. "Hisoblangan" = earned in range.
            earned_period = (
                calculate_earned_period(u, rate_obj, date_from, date_to)
                if rate_obj
                else Decimal("0.00")
            )

            # Payments made within the selected range. Settled payments are kept
            # as history but excluded from the running balance (period close).
            payments = SalaryPayment.objects.filter(user=u, settled=False)
            if date_from:
                payments = payments.filter(occurred_at__date__gte=date_from)
            if date_to:
                payments = payments.filter(occurred_at__date__lte=date_to)
            by_kind = {k: Decimal("0.00") for k in ["salary", "advance", "bonus", "deduction"]}
            for row in payments.values("kind").annotate(total=Sum("amount")):
                by_kind[row["kind"]] = row["total"] or Decimal("0.00")

            # What we still owe for THIS range = earned − (salary + advance +
            # deduction) paid in range. Bonus is discretionary, doesn't reduce debt.
            paid_out = by_kind["salary"] + by_kind["advance"] + by_kind["deduction"]
            remaining = earned_period - paid_out

            last = payments.order_by("-occurred_at").first()

            rate_data = None
            if rate_obj:
                rate_data = {
                    "id": rate_obj.id,
                    "rate_type": rate_obj.rate_type,
                    "rate_type_display": rate_obj.get_rate_type_display(),
                    "rate": str(rate_obj.rate),
                    "currency": rate_obj.currency,
                    "initial_balance": str(rate_obj.initial_balance),
                    "note": rate_obj.note,
                }

            results.append({
                "user_id": u.id,
                "display_name": u.display_name,
                "username": u.username,
                "role": u.role,
                "produced_product_name": (
                    u.produced_product.name if u.produced_product_id else None
                ),
                "rate": rate_data,
                # Earned within the selected range — "Hisoblangan".
                "earned_period": str(earned_period),
                # Payments made within the selected range.
                "paid_salary": str(by_kind["salary"]),
                "paid_advance": str(by_kind["advance"]),
                "paid_bonus": str(by_kind["bonus"]),
                "paid_deduction": str(by_kind["deduction"]),
                "remaining": str(remaining),
                "last_payment": (
                    {
                        "amount": str(last.amount),
                        "currency": last.currency,
                        "kind": last.kind,
                        "kind_display": last.get_kind_display(),
                        "occurred_at": last.occurred_at.isoformat(),
                    }
                    if last
                    else None
                ),
            })

        return Response({"results": results, "count": len(results)})
