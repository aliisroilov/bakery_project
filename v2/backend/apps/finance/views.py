from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone
from rest_framework import filters, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.shops.models import Shop

from .models import (
    CashHandover,
    ExpenseCategory,
    GeneralExpense,
    KassaAccount,
    KassaTransaction,
    KassaTransactionType,
    Payment,
)
from .serializers import (
    CashHandoverSerializer,
    ExpenseCategorySerializer,
    GeneralExpenseSerializer,
    KassaAccountSerializer,
    KassaTransactionSerializer,
    PaymentSerializer,
)


# ─────────────────── Kassa ───────────────────
class KassaAccountViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = KassaAccount.objects.all()
    serializer_class = KassaAccountSerializer


class KassaTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = KassaTransactionSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["occurred_at", "amount"]

    def get_queryset(self):
        qs = KassaTransaction.objects.select_related("account", "created_by")
        p = self.request.query_params
        if account := p.get("account"):
            qs = qs.filter(account_id=account)
        if kind := p.get("kind"):
            qs = qs.filter(kind=kind)
        if currency := p.get("currency"):
            qs = qs.filter(currency=currency)
        if date_from := p.get("date_from"):
            qs = qs.filter(occurred_at__date__gte=date_from)
        if date_to := p.get("date_to"):
            qs = qs.filter(occurred_at__date__lte=date_to)
        return qs


# ─────────────────── Payments (Kirim) ───────────────────
def _apply_payment_to_shop_balance(payment: Payment):
    """Subtract payment.amount + payment.discount from shop's per-currency loan balance."""
    shop = Shop.objects.select_for_update().get(pk=payment.shop_id)
    delta = payment.amount + payment.discount
    if payment.currency == "UZS":
        shop.loan_balance_uzs = F("loan_balance_uzs") - delta
    else:
        shop.loan_balance_usd = F("loan_balance_usd") - delta
    shop.save(update_fields=["loan_balance_uzs", "loan_balance_usd"])


def _apply_payment_to_kassa(payment: Payment):
    """Log the cash into the kassa account — append-only + update cached balance."""
    account = KassaAccount.objects.select_for_update().get(pk=payment.account_id)
    if payment.currency == "UZS":
        account.balance_uzs = F("balance_uzs") + payment.amount
    else:
        account.balance_usd = F("balance_usd") + payment.amount
    account.save(update_fields=["balance_uzs", "balance_usd"])
    KassaTransaction.objects.create(
        account=payment.account,
        kind=KassaTransactionType.PAYMENT_IN
        if payment.payment_type == "collection"
        else KassaTransactionType.LOAN_REPAYMENT,
        currency=payment.currency,
        amount=payment.amount,
        reference_model="finance.Payment",
        reference_id=payment.id,
        note=f"Kirim · {payment.shop.name}",
        occurred_at=payment.received_at,
        created_by=payment.collected_by,
    )


class PaymentViewSet(viewsets.ModelViewSet):
    """
    Kirim = payments received.

    Feature #1: `order_date` lets the user tag payment to a specific delivery day.
    Feature #16: `discount` — on top of the cash amount, also reduces shop debt.
    Feature #20: `collected_by` — dashboard breaks down by collector.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = PaymentSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["received_at", "amount"]

    def get_queryset(self):
        qs = Payment.objects.select_related("shop", "account", "collected_by", "order")
        p = self.request.query_params
        if shop := p.get("shop"):
            qs = qs.filter(shop_id=shop)
        if ptype := p.get("payment_type"):
            qs = qs.filter(payment_type=ptype)
        if currency := p.get("currency"):
            qs = qs.filter(currency=currency)
        if collector := p.get("collected_by"):
            qs = qs.filter(collected_by_id=collector)
        if date_from := p.get("date_from"):
            qs = qs.filter(received_at__date__gte=date_from)
        if date_to := p.get("date_to"):
            qs = qs.filter(received_at__date__lte=date_to)
        return qs

    def perform_create(self, serializer):
        with transaction.atomic():
            payment = serializer.save(
                collected_by=serializer.validated_data.get("collected_by") or self.request.user
            )
            _apply_payment_to_shop_balance(payment)
            _apply_payment_to_kassa(payment)


# ─────────────────── Expenses ───────────────────
class ExpenseCategoryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = ExpenseCategorySerializer
    queryset = ExpenseCategory.objects.all()


class GeneralExpenseViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = GeneralExpenseSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["occurred_at", "amount"]

    def get_queryset(self):
        qs = GeneralExpense.objects.select_related("category", "account", "created_by")
        p = self.request.query_params
        if cat := p.get("category"):
            qs = qs.filter(category_id=cat)
        if currency := p.get("currency"):
            qs = qs.filter(currency=currency)
        if date_from := p.get("date_from"):
            qs = qs.filter(occurred_at__date__gte=date_from)
        if date_to := p.get("date_to"):
            qs = qs.filter(occurred_at__date__lte=date_to)
        return qs

    def perform_create(self, serializer):
        with transaction.atomic():
            exp = serializer.save(created_by=self.request.user)
            account = KassaAccount.objects.select_for_update().get(pk=exp.account_id)
            if exp.currency == "UZS":
                account.balance_uzs = F("balance_uzs") - exp.amount
            else:
                account.balance_usd = F("balance_usd") - exp.amount
            account.save(update_fields=["balance_uzs", "balance_usd"])
            KassaTransaction.objects.create(
                account=exp.account,
                kind=KassaTransactionType.GENERAL_EXPENSE,
                currency=exp.currency,
                amount=-exp.amount,
                reference_model="finance.GeneralExpense",
                reference_id=exp.id,
                note=exp.title,
                occurred_at=exp.occurred_at,
                created_by=self.request.user,
            )


# ─────────────────── Cash Handover (feature #25) ───────────────────
class CashHandoverViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = CashHandoverSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["occurred_at", "amount"]

    def get_queryset(self):
        qs = CashHandover.objects.select_related("driver", "received_by", "to_account")
        p = self.request.query_params
        if driver := p.get("driver"):
            qs = qs.filter(driver_id=driver)
        if date_from := p.get("date_from"):
            qs = qs.filter(occurred_at__date__gte=date_from)
        if date_to := p.get("date_to"):
            qs = qs.filter(occurred_at__date__lte=date_to)
        return qs

    def perform_create(self, serializer):
        with transaction.atomic():
            handover = serializer.save()
            account = KassaAccount.objects.select_for_update().get(pk=handover.to_account_id)
            if handover.currency == "UZS":
                account.balance_uzs = F("balance_uzs") + handover.amount
            else:
                account.balance_usd = F("balance_usd") + handover.amount
            account.save(update_fields=["balance_uzs", "balance_usd"])
            KassaTransaction.objects.create(
                account=handover.to_account,
                kind=KassaTransactionType.CASH_HANDOVER,
                currency=handover.currency,
                amount=handover.amount,
                reference_model="finance.CashHandover",
                reference_id=handover.id,
                note=f"Handover · {handover.driver.display_name}",
                occurred_at=handover.occurred_at,
                created_by=handover.received_by,
            )


class DriverHandoverReportView(APIView):
    """Feature #25: per-driver cash collected vs handed over.

    For each driver (role=driver, is_archived=False), report for the requested
    period (default today):
      - collected: sum of Payment.amount where collected_by=driver
      - handed_over: sum of CashHandover.amount where driver=driver
      - pending: collected − handed_over (cash the driver is still holding)
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        p = request.query_params
        date_from = p.get("date_from")
        date_to = p.get("date_to")
        today = timezone.localdate()
        df = date_from or today.isoformat()
        dt = date_to or today.isoformat()

        User = get_user_model()
        drivers = User.objects.filter(role="driver", is_archived=False).order_by(
            "username"
        )

        results = []
        totals = {
            "collected_uzs": Decimal("0"),
            "collected_usd": Decimal("0"),
            "handed_uzs": Decimal("0"),
            "handed_usd": Decimal("0"),
        }

        for d in drivers:
            payments = Payment.objects.filter(
                collected_by=d,
                received_at__date__gte=df,
                received_at__date__lte=dt,
            )
            handovers = CashHandover.objects.filter(
                driver=d,
                occurred_at__date__gte=df,
                occurred_at__date__lte=dt,
            )

            collected_uzs = (
                payments.filter(currency="UZS").aggregate(s=Sum("amount"))["s"]
                or Decimal("0")
            )
            collected_usd = (
                payments.filter(currency="USD").aggregate(s=Sum("amount"))["s"]
                or Decimal("0")
            )
            handed_uzs = (
                handovers.filter(currency="UZS").aggregate(s=Sum("amount"))["s"]
                or Decimal("0")
            )
            handed_usd = (
                handovers.filter(currency="USD").aggregate(s=Sum("amount"))["s"]
                or Decimal("0")
            )
            totals["collected_uzs"] += collected_uzs
            totals["collected_usd"] += collected_usd
            totals["handed_uzs"] += handed_uzs
            totals["handed_usd"] += handed_usd

            results.append(
                {
                    "driver_id": d.id,
                    "driver_name": d.display_name,
                    "username": d.username,
                    "collected_uzs": str(collected_uzs),
                    "collected_usd": str(collected_usd),
                    "handed_uzs": str(handed_uzs),
                    "handed_usd": str(handed_usd),
                    "pending_uzs": str(collected_uzs - handed_uzs),
                    "pending_usd": str(collected_usd - handed_usd),
                    "payment_count": payments.count(),
                    "handover_count": handovers.count(),
                }
            )

        return Response(
            {
                "date_from": df,
                "date_to": dt,
                "results": results,
                "count": len(results),
                "totals": {k: str(v) for k, v in totals.items()},
            }
        )
