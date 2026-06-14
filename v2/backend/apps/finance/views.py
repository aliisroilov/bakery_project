from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, F, Sum
from django.utils import timezone
from rest_framework import filters, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import ReadOrManagerWrite
from apps.shops.models import Shop

from .models import (
    CashHandover,
    ExpenseCategory,
    GeneralExpense,
    KassaAccount,
    KassaTransaction,
    KassaTransactionType,
    KassaTransfer,
    Payment,
)
from .serializers import (
    CashHandoverSerializer,
    ExpenseCategorySerializer,
    GeneralExpenseSerializer,
    KassaAccountSerializer,
    KassaTransactionSerializer,
    KassaTransferSerializer,
    PaymentSerializer,
)


# ─────────────────── Kassa ───────────────────
class KassaAccountViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = KassaAccount.objects.all()
    serializer_class = KassaAccountSerializer


class KassaTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [ReadOrManagerWrite]
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
    permission_classes = [ReadOrManagerWrite]
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

    def perform_update(self, serializer):
        with transaction.atomic():
            old = serializer.instance
            old_amount = old.amount
            old_discount = old.discount
            old_currency = old.currency
            old_account_id = old.account_id
            old_shop_id = old.shop_id

            payment = serializer.save()

            # Reverse old shop balance change.
            old_shop = Shop.objects.select_for_update().get(pk=old_shop_id)
            old_delta = old_amount + old_discount
            if old_currency == "UZS":
                old_shop.loan_balance_uzs = F("loan_balance_uzs") + old_delta
            else:
                old_shop.loan_balance_usd = F("loan_balance_usd") + old_delta
            old_shop.save(update_fields=["loan_balance_uzs", "loan_balance_usd"])

            # Apply new shop balance change.
            _apply_payment_to_shop_balance(payment)

            # Lock both KassaAccounts in deterministic (sorted) order to prevent
            # deadlocks when two concurrent updates swap old/new accounts.
            acct_ids = sorted({old_account_id, payment.account_id})
            accounts = {
                a.id: a
                for a in KassaAccount.objects.select_for_update().filter(id__in=acct_ids)
            }

            # Reverse old kassa credit.
            old_account = accounts[old_account_id]
            if old_currency == "UZS":
                old_account.balance_uzs = F("balance_uzs") - old_amount
            else:
                old_account.balance_usd = F("balance_usd") - old_amount
            old_account.save(update_fields=["balance_uzs", "balance_usd"])

            # Apply new kassa credit.
            new_account = accounts[payment.account_id]
            if payment.currency == "UZS":
                new_account.balance_uzs = F("balance_uzs") + payment.amount
            else:
                new_account.balance_usd = F("balance_usd") + payment.amount
            new_account.save(update_fields=["balance_uzs", "balance_usd"])

            # Update linked KassaTransaction.
            KassaTransaction.objects.filter(
                reference_model="finance.Payment",
                reference_id=payment.id,
            ).update(
                account=payment.account,
                currency=payment.currency,
                amount=payment.amount,
                occurred_at=payment.received_at,
            )

    def perform_destroy(self, instance):
        with transaction.atomic():
            # Reverse shop balance change.
            shop = Shop.objects.select_for_update().get(pk=instance.shop_id)
            delta = instance.amount + instance.discount
            if instance.currency == "UZS":
                shop.loan_balance_uzs = F("loan_balance_uzs") + delta
            else:
                shop.loan_balance_usd = F("loan_balance_usd") + delta
            shop.save(update_fields=["loan_balance_uzs", "loan_balance_usd"])

            # Reverse kassa credit.
            account = KassaAccount.objects.select_for_update().get(pk=instance.account_id)
            if instance.currency == "UZS":
                account.balance_uzs = F("balance_uzs") - instance.amount
            else:
                account.balance_usd = F("balance_usd") - instance.amount
            account.save(update_fields=["balance_uzs", "balance_usd"])

            KassaTransaction.objects.filter(
                reference_model="finance.Payment",
                reference_id=instance.id,
            ).delete()
            instance.delete()


# ─────────────────── Expenses ───────────────────
class ExpenseCategoryViewSet(viewsets.ModelViewSet):
    permission_classes = [ReadOrManagerWrite]
    serializer_class = ExpenseCategorySerializer
    queryset = ExpenseCategory.objects.all()


class GeneralExpenseViewSet(viewsets.ModelViewSet):
    permission_classes = [ReadOrManagerWrite]
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

    def perform_update(self, serializer):
        with transaction.atomic():
            old = serializer.instance
            old_amount = old.amount
            old_currency = old.currency
            old_account_id = old.account_id

            exp = serializer.save()

            # Reverse old deduction from old account.
            old_account = KassaAccount.objects.select_for_update().get(pk=old_account_id)
            if old_currency == "UZS":
                old_account.balance_uzs = F("balance_uzs") + old_amount
            else:
                old_account.balance_usd = F("balance_usd") + old_amount
            old_account.save(update_fields=["balance_uzs", "balance_usd"])

            # Apply new deduction to (possibly new) account.
            new_account = KassaAccount.objects.select_for_update().get(pk=exp.account_id)
            if exp.currency == "UZS":
                new_account.balance_uzs = F("balance_uzs") - exp.amount
            else:
                new_account.balance_usd = F("balance_usd") - exp.amount
            new_account.save(update_fields=["balance_uzs", "balance_usd"])

            # Update linked KassaTransaction.
            KassaTransaction.objects.filter(
                reference_model="finance.GeneralExpense",
                reference_id=exp.id,
            ).update(
                account=exp.account,
                currency=exp.currency,
                amount=-exp.amount,
                note=exp.title,
                occurred_at=exp.occurred_at,
            )

    def perform_destroy(self, instance):
        with transaction.atomic():
            account = KassaAccount.objects.select_for_update().get(pk=instance.account_id)
            if instance.currency == "UZS":
                account.balance_uzs = F("balance_uzs") + instance.amount
            else:
                account.balance_usd = F("balance_usd") + instance.amount
            account.save(update_fields=["balance_uzs", "balance_usd"])
            KassaTransaction.objects.filter(
                reference_model="finance.GeneralExpense",
                reference_id=instance.id,
            ).delete()
            instance.delete()


# ─────────────────── Cash Handover (feature #25) ───────────────────
class CashHandoverViewSet(viewsets.ModelViewSet):
    permission_classes = [ReadOrManagerWrite]
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
            received_by = serializer.validated_data.get("received_by") or self.request.user
            handover = serializer.save(received_by=received_by)
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

    def perform_update(self, serializer):
        with transaction.atomic():
            old = serializer.instance
            old_amount = Decimal(str(old.amount))
            old_currency = old.currency
            old_account_id = old.to_account_id

            handover = serializer.save()

            # Reverse old balance on old account.
            old_account = KassaAccount.objects.select_for_update().get(pk=old_account_id)
            if old_currency == "UZS":
                old_account.balance_uzs = F("balance_uzs") - old_amount
            else:
                old_account.balance_usd = F("balance_usd") - old_amount
            old_account.save(update_fields=["balance_uzs", "balance_usd"])

            # Apply new balance to (possibly changed) account.
            new_account = KassaAccount.objects.select_for_update().get(pk=handover.to_account_id)
            if handover.currency == "UZS":
                new_account.balance_uzs = F("balance_uzs") + handover.amount
            else:
                new_account.balance_usd = F("balance_usd") + handover.amount
            new_account.save(update_fields=["balance_uzs", "balance_usd"])

            # Sync the linked KassaTransaction row.
            KassaTransaction.objects.filter(
                reference_model="finance.CashHandover",
                reference_id=handover.id,
            ).update(
                account=handover.to_account,
                currency=handover.currency,
                amount=handover.amount,
                occurred_at=handover.occurred_at,
                note=f"Handover · {handover.driver.display_name}",
            )

    def perform_destroy(self, instance):
        with transaction.atomic():
            account = KassaAccount.objects.select_for_update().get(pk=instance.to_account_id)
            if instance.currency == "UZS":
                account.balance_uzs = F("balance_uzs") - instance.amount
            else:
                account.balance_usd = F("balance_usd") - instance.amount
            account.save(update_fields=["balance_uzs", "balance_usd"])
            KassaTransaction.objects.filter(
                reference_model="finance.CashHandover",
                reference_id=instance.id,
            ).delete()
            instance.delete()


class KassaTransferViewSet(viewsets.ModelViewSet):
    """
    Transfer cash between KassaAccounts (e.g. Rizoxon → Seyf).

    On create:  debit from_account, credit to_account, write two ledger rows.
    On update:  reverse old balances, apply new balances, sync both ledger rows.
    On destroy: reverse both balance changes and delete the ledger rows.
    """

    permission_classes = [ReadOrManagerWrite]
    serializer_class = KassaTransferSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["occurred_at", "amount"]

    def get_queryset(self):
        qs = KassaTransfer.objects.select_related(
            "from_account", "to_account", "created_by"
        )
        p = self.request.query_params
        if date_from := p.get("date_from"):
            qs = qs.filter(occurred_at__date__gte=date_from)
        if date_to := p.get("date_to"):
            qs = qs.filter(occurred_at__date__lte=date_to)
        return qs

    def perform_create(self, serializer):
        with transaction.atomic():
            transfer = serializer.save(created_by=self.request.user)

            # Debit source account.
            src = KassaAccount.objects.select_for_update().get(pk=transfer.from_account_id)
            if transfer.currency == "UZS":
                src.balance_uzs = F("balance_uzs") - transfer.amount
            else:
                src.balance_usd = F("balance_usd") - transfer.amount
            src.save(update_fields=["balance_uzs", "balance_usd"])

            # Credit destination account.
            dst = KassaAccount.objects.select_for_update().get(pk=transfer.to_account_id)
            if transfer.currency == "UZS":
                dst.balance_uzs = F("balance_uzs") + transfer.amount
            else:
                dst.balance_usd = F("balance_usd") + transfer.amount
            dst.save(update_fields=["balance_uzs", "balance_usd"])

            ref_note = transfer.note or f"{transfer.from_account.name} → {transfer.to_account.name}"

            # Debit ledger row on source.
            KassaTransaction.objects.create(
                account=transfer.from_account,
                kind=KassaTransactionType.TRANSFER,
                currency=transfer.currency,
                amount=-transfer.amount,
                reference_model="finance.KassaTransfer",
                reference_id=transfer.id,
                note=f"O'tkazma → {transfer.to_account.name}" + (f" · {transfer.note}" if transfer.note else ""),
                occurred_at=transfer.occurred_at,
                created_by=self.request.user,
            )
            # Credit ledger row on destination.
            KassaTransaction.objects.create(
                account=transfer.to_account,
                kind=KassaTransactionType.TRANSFER,
                currency=transfer.currency,
                amount=transfer.amount,
                reference_model="finance.KassaTransfer",
                reference_id=transfer.id,
                note=f"O'tkazma ← {transfer.from_account.name}" + (f" · {transfer.note}" if transfer.note else ""),
                occurred_at=transfer.occurred_at,
                created_by=self.request.user,
            )

    def perform_update(self, serializer):
        with transaction.atomic():
            old = serializer.instance
            old_amount = Decimal(str(old.amount))
            old_currency = old.currency
            old_from_id = old.from_account_id
            old_to_id = old.to_account_id

            transfer = serializer.save()

            # Reverse old: re-add to source, remove from destination.
            old_src = KassaAccount.objects.select_for_update().get(pk=old_from_id)
            if old_currency == "UZS":
                old_src.balance_uzs = F("balance_uzs") + old_amount
            else:
                old_src.balance_usd = F("balance_usd") + old_amount
            old_src.save(update_fields=["balance_uzs", "balance_usd"])

            old_dst = KassaAccount.objects.select_for_update().get(pk=old_to_id)
            if old_currency == "UZS":
                old_dst.balance_uzs = F("balance_uzs") - old_amount
            else:
                old_dst.balance_usd = F("balance_usd") - old_amount
            old_dst.save(update_fields=["balance_uzs", "balance_usd"])

            # Apply new: deduct from new source, credit new destination.
            new_src = KassaAccount.objects.select_for_update().get(pk=transfer.from_account_id)
            if transfer.currency == "UZS":
                new_src.balance_uzs = F("balance_uzs") - transfer.amount
            else:
                new_src.balance_usd = F("balance_usd") - transfer.amount
            new_src.save(update_fields=["balance_uzs", "balance_usd"])

            new_dst = KassaAccount.objects.select_for_update().get(pk=transfer.to_account_id)
            if transfer.currency == "UZS":
                new_dst.balance_uzs = F("balance_uzs") + transfer.amount
            else:
                new_dst.balance_usd = F("balance_usd") + transfer.amount
            new_dst.save(update_fields=["balance_uzs", "balance_usd"])

            # Sync both linked KassaTransaction rows (debit row has amount<0).
            KassaTransaction.objects.filter(
                reference_model="finance.KassaTransfer",
                reference_id=transfer.id,
                amount__lt=0,
            ).update(
                account=transfer.from_account,
                currency=transfer.currency,
                amount=-transfer.amount,
                occurred_at=transfer.occurred_at,
                note=f"O'tkazma → {transfer.to_account.name}" + (f" · {transfer.note}" if transfer.note else ""),
            )
            KassaTransaction.objects.filter(
                reference_model="finance.KassaTransfer",
                reference_id=transfer.id,
                amount__gt=0,
            ).update(
                account=transfer.to_account,
                currency=transfer.currency,
                amount=transfer.amount,
                occurred_at=transfer.occurred_at,
                note=f"O'tkazma ← {transfer.from_account.name}" + (f" · {transfer.note}" if transfer.note else ""),
            )

    def perform_destroy(self, instance):
        with transaction.atomic():
            # Reverse source debit.
            src = KassaAccount.objects.select_for_update().get(pk=instance.from_account_id)
            if instance.currency == "UZS":
                src.balance_uzs = F("balance_uzs") + instance.amount
            else:
                src.balance_usd = F("balance_usd") + instance.amount
            src.save(update_fields=["balance_uzs", "balance_usd"])

            # Reverse destination credit.
            dst = KassaAccount.objects.select_for_update().get(pk=instance.to_account_id)
            if instance.currency == "UZS":
                dst.balance_uzs = F("balance_uzs") - instance.amount
            else:
                dst.balance_usd = F("balance_usd") - instance.amount
            dst.save(update_fields=["balance_uzs", "balance_usd"])

            KassaTransaction.objects.filter(
                reference_model="finance.KassaTransfer",
                reference_id=instance.id,
            ).delete()
            instance.delete()


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
        drivers = list(
            User.objects.filter(role="driver", is_archived=False).order_by("username")
        )
        driver_ids = [d.id for d in drivers]

        # Two queries total (previously N×4 per driver).
        payment_aggs = (
            Payment.objects.filter(
                collected_by_id__in=driver_ids,
                received_at__date__gte=df,
                received_at__date__lte=dt,
            )
            .values("collected_by_id", "currency")
            .annotate(total=Sum("amount"), count=Count("id"))
        )
        handover_aggs = (
            CashHandover.objects.filter(
                driver_id__in=driver_ids,
                occurred_at__date__gte=df,
                occurred_at__date__lte=dt,
            )
            .values("driver_id", "currency")
            .annotate(total=Sum("amount"), count=Count("id"))
        )

        # Build per-driver lookup dicts.
        p_map: dict = {}
        for row in payment_aggs:
            p_map.setdefault(row["collected_by_id"], {})[row["currency"]] = row

        h_map: dict = {}
        for row in handover_aggs:
            h_map.setdefault(row["driver_id"], {})[row["currency"]] = row

        results = []
        totals = {
            "collected_uzs": Decimal("0"),
            "collected_usd": Decimal("0"),
            "handed_uzs": Decimal("0"),
            "handed_usd": Decimal("0"),
        }

        for d in drivers:
            dp = p_map.get(d.id, {})
            dh = h_map.get(d.id, {})
            collected_uzs = dp.get("UZS", {}).get("total") or Decimal("0")
            collected_usd = dp.get("USD", {}).get("total") or Decimal("0")
            handed_uzs = dh.get("UZS", {}).get("total") or Decimal("0")
            handed_usd = dh.get("USD", {}).get("total") or Decimal("0")
            payment_count = sum(v["count"] for v in dp.values())
            handover_count = sum(v["count"] for v in dh.values())

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
                    "payment_count": payment_count,
                    "handover_count": handover_count,
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
