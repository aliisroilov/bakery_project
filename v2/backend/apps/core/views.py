"""Core views — dashboard summary + misc cross-app endpoints."""
from datetime import datetime, time

from django.db.models import Sum, F, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.finance.models import (
    GeneralExpense,
    KassaAccount,
    Payment,
)
from apps.inventory.models import Ingredient, Purchase as IngredientPurchase
from apps.orders.models import Order, OrderPriority, OrderStatus
from apps.production.models import Production
from apps.salary.models import SalaryPayment
from apps.shops.models import Shop


def _today_bounds():
    """Return (start_of_day, end_of_day) in the server timezone."""
    now = timezone.localtime()
    start = timezone.make_aware(datetime.combine(now.date(), time.min))
    end = timezone.make_aware(datetime.combine(now.date(), time.max))
    return start, end


def _month_start():
    now = timezone.localtime()
    return timezone.make_aware(datetime.combine(now.date().replace(day=1), time.min))


class DashboardSummaryView(APIView):
    """
    Aggregated today/month figures for the home dashboard.

    Shape — never sums UZS + USD together (feature #9).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        today_start, today_end = _today_bounds()
        month_start = _month_start()

        # ── Kassa balances (Seyf + Rizoxon) ─────────────────────────
        accounts = [
            {
                "slug": a.slug,
                "name": a.name,
                "balance_uzs": str(a.balance_uzs),
                "balance_usd": str(a.balance_usd),
            }
            for a in KassaAccount.objects.all()
        ]

        # ── Today's kirim (payments received today) ─────────────────
        today_payments = Payment.objects.filter(
            received_at__range=(today_start, today_end)
        )
        kirim_today_uzs = today_payments.filter(currency="UZS").aggregate(
            s=Sum("amount")
        )["s"] or 0
        kirim_today_usd = today_payments.filter(currency="USD").aggregate(
            s=Sum("amount")
        )["s"] or 0

        # Per-collector breakdown (feature #20)
        collectors = (
            today_payments
            .values("collected_by", "collected_by__username", "collected_by__full_name", "currency")
            .annotate(total=Sum("amount"))
            .order_by("-total")
        )
        by_collector: dict[int, dict] = {}
        for row in collectors:
            uid = row["collected_by"] or 0
            name = row["collected_by__full_name"] or row["collected_by__username"] or "—"
            entry = by_collector.setdefault(uid, {"user_id": uid or None, "name": name, "uzs": "0", "usd": "0"})
            if row["currency"] == "UZS":
                entry["uzs"] = str(row["total"] or 0)
            else:
                entry["usd"] = str(row["total"] or 0)

        # ── Today's and month's production (feature #13) ────────────
        prod_today = Production.objects.filter(
            occurred_at__range=(today_start, today_end)
        ).aggregate(meshok=Sum("meshok_count"), units=Sum("unit_count"))
        prod_month = Production.objects.filter(
            occurred_at__gte=month_start
        ).aggregate(meshok=Sum("meshok_count"), units=Sum("unit_count"))

        # Per-product breakdown today
        prod_by_product = list(
            Production.objects.filter(occurred_at__range=(today_start, today_end))
            .values("product__id", "product__name")
            .annotate(meshok=Sum("meshok_count"), units=Sum("unit_count"))
            .order_by("-meshok")
        )

        # ── Urgent / high-priority pending orders (feature #6) ──────
        urgent_qs = (
            Order.objects
            .filter(status__in=[OrderStatus.PENDING, OrderStatus.PARTIALLY_DELIVERED])
            .filter(Q(priority=OrderPriority.URGENT) | Q(priority=OrderPriority.HIGH))
            .select_related("shop")
            .order_by("-priority", "delivery_time")[:10]
        )
        urgent = [
            {
                "id": o.id,
                "shop_name": o.shop.name,
                "priority": o.priority,
                "delivery_time": o.delivery_time,
                "order_date": o.order_date,
                "status": o.status,
            }
            for o in urgent_qs
        ]

        # ── Shops over loan limit (feature #5) ──────────────────────
        over_limit_qs = (
            Shop.objects
            .filter(is_archived=False)
            .filter(
                Q(loan_limit_uzs__gt=0, loan_balance_uzs__gt=F("loan_limit_uzs"))
                | Q(loan_limit_usd__gt=0, loan_balance_usd__gt=F("loan_limit_usd"))
            )
        )
        over_limit = [
            {
                "id": s.id,
                "name": s.name,
                "loan_balance_uzs": str(s.loan_balance_uzs),
                "loan_balance_usd": str(s.loan_balance_usd),
                "loan_limit_uzs": str(s.loan_limit_uzs),
                "loan_limit_usd": str(s.loan_limit_usd),
            }
            for s in over_limit_qs
        ]

        # ── Open orders count ───────────────────────────────────────
        open_orders = Order.objects.filter(
            status__in=[OrderStatus.PENDING, OrderStatus.PARTIALLY_DELIVERED]
        ).count()

        # ── Today's order counts by status (v1 parity) ──────────────
        today_orders = Order.objects.filter(order_date=timezone.localdate())
        orders_today_total = today_orders.count()
        orders_today_pending = today_orders.filter(status=OrderStatus.PENDING).count()
        orders_today_partial = today_orders.filter(
            status=OrderStatus.PARTIALLY_DELIVERED
        ).count()
        orders_today_delivered = today_orders.filter(
            status=OrderStatus.DELIVERED
        ).count()

        # ── Total loan across shops (both currencies) ───────────────
        totals = Shop.objects.filter(is_archived=False).aggregate(
            uzs=Sum("loan_balance_uzs"),
            usd=Sum("loan_balance_usd"),
        )

        # ── Net income today (feature #11) ──────────────────────────
        # Formula: revenue (kirim) - all cash outflows for the day
        # Revenue = payments received today (closes_loan_by: cash + discount contributes separately)
        # Expenses = ingredient purchases + general expenses + salary payouts
        # Computed per currency (UZS + USD kept separate).
        def _sum_today(qs, field="amount"):
            uzs = qs.filter(currency="UZS").aggregate(s=Sum(field))["s"] or 0
            usd = qs.filter(currency="USD").aggregate(s=Sum(field))["s"] or 0
            return uzs, usd

        purchases_today = IngredientPurchase.objects.filter(
            occurred_at__range=(today_start, today_end)
        )
        purchase_uzs, purchase_usd = _sum_today(purchases_today, "total_price")

        expenses_today = GeneralExpense.objects.filter(
            occurred_at__range=(today_start, today_end)
        )
        expense_uzs, expense_usd = _sum_today(expenses_today)

        salary_today = SalaryPayment.objects.filter(
            occurred_at__range=(today_start, today_end)
        ).exclude(kind="deduction")
        salary_uzs, salary_usd = _sum_today(salary_today)

        net_uzs = (kirim_today_uzs or 0) - (purchase_uzs + expense_uzs + salary_uzs)
        net_usd = (kirim_today_usd or 0) - (purchase_usd + expense_usd + salary_usd)

        return Response(
            {
                "accounts": accounts,
                "kirim_today": {
                    "uzs": str(kirim_today_uzs),
                    "usd": str(kirim_today_usd),
                    "by_collector": list(by_collector.values()),
                },
                "orders_today": {
                    "total": orders_today_total,
                    "pending": orders_today_pending,
                    "partial": orders_today_partial,
                    "delivered": orders_today_delivered,
                },
                "loans_total": {
                    "uzs": str(totals["uzs"] or 0),
                    "usd": str(totals["usd"] or 0),
                },
                "production": {
                    "today": {
                        "meshok": str(prod_today["meshok"] or 0),
                        "units": str(prod_today["units"] or 0),
                    },
                    "month": {
                        "meshok": str(prod_month["meshok"] or 0),
                        "units": str(prod_month["units"] or 0),
                    },
                    "today_by_product": [
                        {
                            "product_id": r["product__id"],
                            "product_name": r["product__name"],
                            "meshok": str(r["meshok"] or 0),
                            "units": str(r["units"] or 0),
                        }
                        for r in prod_by_product
                    ],
                },
                "urgent_orders": urgent,
                "over_loan_limit": over_limit,
                "open_orders_count": open_orders,
                "net_income_today": {
                    "uzs": str(net_uzs),
                    "usd": str(net_usd),
                    "revenue_uzs": str(kirim_today_uzs),
                    "revenue_usd": str(kirim_today_usd),
                    "expenses_uzs": str(purchase_uzs + expense_uzs + salary_uzs),
                    "expenses_usd": str(purchase_usd + expense_usd + salary_usd),
                    "breakdown": {
                        "purchases_uzs": str(purchase_uzs),
                        "purchases_usd": str(purchase_usd),
                        "general_expenses_uzs": str(expense_uzs),
                        "general_expenses_usd": str(expense_usd),
                        "salary_uzs": str(salary_uzs),
                        "salary_usd": str(salary_usd),
                    },
                },
            },
            status=status.HTTP_200_OK,
        )


class NotificationsView(APIView):
    """
    Feature #10: real-time notifications (loan-limit exceeded + low stock).

    Computed on-the-fly from current state — no stored notification model.
    Frontend polls this to update the bell badge.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        low_stock = (
            Ingredient.objects
            .filter(is_archived=False, low_stock_threshold__gt=0)
            .filter(quantity__lte=F("low_stock_threshold"))
            .select_related("unit")
        )
        low_stock_items = [
            {
                "id": i.id,
                "kind": "low_stock",
                "ingredient_id": i.id,
                "name": i.name,
                "quantity": str(i.quantity),
                "threshold": str(i.low_stock_threshold),
                "unit": i.unit.short if i.unit_id else "",
            }
            for i in low_stock
        ]

        over_limit_qs = (
            Shop.objects
            .filter(is_archived=False)
            .filter(
                Q(loan_limit_uzs__gt=0, loan_balance_uzs__gt=F("loan_limit_uzs"))
                | Q(loan_limit_usd__gt=0, loan_balance_usd__gt=F("loan_limit_usd"))
            )
        )
        over_limit_items = []
        for s in over_limit_qs:
            uzs_over = s.loan_limit_uzs and s.loan_balance_uzs > s.loan_limit_uzs
            usd_over = s.loan_limit_usd and s.loan_balance_usd > s.loan_limit_usd
            over_limit_items.append(
                {
                    "id": s.id,
                    "kind": "loan_limit",
                    "shop_id": s.id,
                    "name": s.name,
                    "loan_balance_uzs": str(s.loan_balance_uzs),
                    "loan_limit_uzs": str(s.loan_limit_uzs),
                    "loan_balance_usd": str(s.loan_balance_usd),
                    "loan_limit_usd": str(s.loan_limit_usd),
                    "uzs_over": bool(uzs_over),
                    "usd_over": bool(usd_over),
                }
            )

        return Response(
            {
                "count": len(low_stock_items) + len(over_limit_items),
                "low_stock": low_stock_items,
                "loan_limit": over_limit_items,
            }
        )
