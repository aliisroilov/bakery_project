from decimal import Decimal

from django.db import transaction
from django.db.models import F, Sum
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.shops.models import Shop

from .models import Order, OrderItem, OrderStatus
from .serializers import (
    ConfirmDeliveryItemSerializer,
    OrderCreateSerializer,
    OrderDetailSerializer,
    OrderListSerializer,
)


class OrderViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["shop__name", "note"]
    ordering_fields = ["order_date", "priority", "status", "created_at"]

    def get_queryset(self):
        qs = (
            Order.objects
            .select_related("shop", "created_by")
            .prefetch_related("items", "items__product")
        )
        params = self.request.query_params
        if shop := params.get("shop"):
            qs = qs.filter(shop_id=shop)
        if st := params.get("status"):
            qs = qs.filter(status=st)
        if pr := params.get("priority"):
            qs = qs.filter(priority=pr)
        if date := params.get("date"):
            qs = qs.filter(order_date=date)
        if date_from := params.get("date_from"):
            qs = qs.filter(order_date__gte=date_from)
        if date_to := params.get("date_to"):
            qs = qs.filter(order_date__lte=date_to)
        # Default ordering: pending orders first by delivery_time (soonest first,
        # no-time last), then most recent order_date. Explicit ?ordering= wins.
        if not params.get("ordering"):
            qs = qs.order_by(
                F("delivery_time").asc(nulls_last=True),
                "-order_date",
                "-id",
            )
        return qs

    def get_serializer_class(self):
        if self.action in ("retrieve",):
            return OrderDetailSerializer
        return OrderListSerializer

    def create(self, request):
        ser = OrderCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        with transaction.atomic():
            order = Order.objects.create(
                shop_id=data["shop"],
                order_date=data["order_date"],
                delivery_time=data.get("delivery_time"),
                priority=data.get("priority", "normal"),
                currency=data.get("currency", "UZS"),
                note=data.get("note", ""),
                created_by=request.user if request.user.is_authenticated else None,
            )
            for item in data["items"]:
                OrderItem.objects.create(
                    order=order,
                    product_id=item["product"],
                    unit_price=item["unit_price"],
                    quantity=item["quantity"],
                )
        return Response(
            OrderDetailSerializer(order).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def confirm_delivery(self, request, pk=None):
        """
        Confirm how much of each item was delivered (and optionally returned — feature #17).

        Body: { "items": [{ "item_id": n, "delivered_quantity": n, "returned_quantity": n }, ...] }

        Updates item rows, recomputes shop loan balance for this currency, sets order status.
        """
        order = self.get_object()
        ser = ConfirmDeliveryItemSerializer(data=request.data.get("items", []), many=True)
        ser.is_valid(raise_exception=True)

        with transaction.atomic():
            # Lock the order + shop rows.
            order = Order.objects.select_for_update().get(pk=order.pk)
            shop = Shop.objects.select_for_update().get(pk=order.shop_id)

            # Ported from v1: when delivered_quantity changes we also adjust
            # finished-goods stock. Net delivered = delivered - returned; we
            # diff this vs the previously-recorded net and apply the delta.
            from apps.production.models import BakeryProductStock

            items_by_id = {i.id: i for i in order.items.all()}
            for row in ser.validated_data:
                item = items_by_id.get(row["item_id"])
                if not item or item.order_id != order.id:
                    continue
                delivered = min(row["delivered_quantity"], item.quantity)
                returned = min(row.get("returned_quantity", 0), delivered)
                old_net = max(item.delivered_quantity - item.returned_quantity, 0)
                new_net = max(delivered - returned, 0)
                delta = new_net - old_net
                item.delivered_quantity = delivered
                item.returned_quantity = returned
                item.save(update_fields=["delivered_quantity", "returned_quantity"])

                if delta != 0:
                    stock, _ = BakeryProductStock.objects.get_or_create(
                        product_id=item.product_id
                    )
                    BakeryProductStock.objects.filter(pk=stock.pk).update(
                        quantity=F("quantity") - delta
                    )

            # Recompute this order's status from items.
            items = list(order.items.all())
            all_delivered = items and all(
                i.delivered_quantity >= i.quantity for i in items
            )
            some_delivered = any(i.delivered_quantity > 0 for i in items)
            if all_delivered:
                order.status = OrderStatus.DELIVERED
            elif some_delivered:
                order.status = OrderStatus.PARTIALLY_DELIVERED
            else:
                order.status = OrderStatus.PENDING
            order.save(update_fields=["status"])

            # Recompute shop loan balance *for this currency* from scratch.
            # Sum delivered_value across all shop orders - sum payments.
            delivered_total = Decimal("0")
            for o in Order.objects.filter(shop=shop, currency=order.currency).prefetch_related("items"):
                for it in o.items.all():
                    delivered_total += it.delivered_price

            from apps.finance.models import Payment
            paid_total = (
                Payment.objects
                .filter(shop=shop, currency=order.currency)
                .aggregate(s=Sum("amount"))["s"] or Decimal("0")
            )
            discount_total = (
                Payment.objects
                .filter(shop=shop, currency=order.currency)
                .aggregate(s=Sum("discount"))["s"] or Decimal("0")
            )

            new_balance = delivered_total - paid_total - discount_total
            if order.currency == "UZS":
                shop.loan_balance_uzs = new_balance
            else:
                shop.loan_balance_usd = new_balance
            shop.save(update_fields=["loan_balance_uzs", "loan_balance_usd"])

        return Response(OrderDetailSerializer(order).data)

    @action(detail=True, methods=["post"])
    def repeat(self, request, pk=None):
        """Feature #3 — clone this order as a new PENDING order for the same shop."""
        source = self.get_object()
        from django.utils import timezone
        with transaction.atomic():
            new_order = Order.objects.create(
                shop=source.shop,
                order_date=timezone.localdate(),
                delivery_time=source.delivery_time,
                priority=source.priority,
                currency=source.currency,
                status=OrderStatus.PENDING,
                note=source.note,
                created_by=request.user if request.user.is_authenticated else None,
            )
            for item in source.items.all():
                OrderItem.objects.create(
                    order=new_order,
                    product=item.product,
                    unit_price=item.unit_price,
                    quantity=item.quantity,
                )
        return Response(
            OrderDetailSerializer(new_order).data,
            status=status.HTTP_201_CREATED,
        )
