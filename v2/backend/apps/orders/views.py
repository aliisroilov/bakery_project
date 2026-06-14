from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.production.models import BakeryProductStock
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
        if region := params.get("region"):
            qs = qs.filter(shop__region_id=region)
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
        chosen_status = data.get("status", OrderStatus.PENDING)

        with transaction.atomic():
            order = Order.objects.create(
                shop_id=data["shop"],
                order_date=data["order_date"],
                delivery_time=data.get("delivery_time"),
                priority=data.get("priority", "normal"),
                status=chosen_status,
                currency=data.get("currency", "UZS"),
                note=data.get("note", ""),
                created_by=request.user if request.user.is_authenticated else None,
            )
            items = []
            for item_data in data["items"]:
                oi = OrderItem.objects.create(
                    order=order,
                    product_id=item_data["product"],
                    unit_price=item_data["unit_price"],
                    quantity=item_data["quantity"],
                )
                # Carry the optional inline delivered_quantity for the step below.
                oi._delivered_input = item_data.get("delivered_quantity")
                items.append(oi)

            # Inline delivery — handle both DELIVERED (full unless overridden) and
            # PARTIALLY_DELIVERED (per-item delivered_quantity entered in the form).
            # This bumps finished-goods stock and the shop loan balance, then
            # recomputes the real status from what was actually delivered.
            if chosen_status in (OrderStatus.DELIVERED, OrderStatus.PARTIALLY_DELIVERED):
                shop = Shop.objects.select_for_update().get(pk=order.shop_id)
                balance_delta = Decimal("0")
                for oi in items:
                    if chosen_status == OrderStatus.DELIVERED and oi._delivered_input is None:
                        delivered = oi.quantity
                    else:
                        delivered = min(int(oi._delivered_input or 0), oi.quantity)
                    if delivered <= 0:
                        continue
                    oi.delivered_quantity = delivered
                    oi.save(update_fields=["delivered_quantity"])
                    stock, _ = BakeryProductStock.objects.get_or_create(product_id=oi.product_id)
                    BakeryProductStock.objects.filter(pk=stock.pk).update(
                        quantity=F("quantity") - Decimal(str(delivered))
                    )
                    balance_delta += Decimal(str(delivered)) * oi.unit_price
                if balance_delta != 0:
                    if order.currency == "UZS":
                        shop.loan_balance_uzs = F("loan_balance_uzs") + balance_delta
                    else:
                        shop.loan_balance_usd = F("loan_balance_usd") + balance_delta
                    shop.save(update_fields=["loan_balance_uzs", "loan_balance_usd"])

                # Recompute status from actual delivered amounts (e.g. a "partial"
                # where every line was filled becomes DELIVERED, and vice versa).
                all_delivered = items and all(
                    oi.delivered_quantity >= oi.quantity for oi in items
                )
                some_delivered = any(oi.delivered_quantity > 0 for oi in items)
                new_status = (
                    OrderStatus.DELIVERED if all_delivered
                    else OrderStatus.PARTIALLY_DELIVERED if some_delivered
                    else OrderStatus.PENDING
                )
                if new_status != order.status:
                    order.status = new_status
                    order.save(update_fields=["status"])

        return Response(
            OrderDetailSerializer(order).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        order = self.get_object()

        # Split request data: items handled separately, rest goes to serializer.
        items_data = request.data.get("items")

        with transaction.atomic():
            order_locked = Order.objects.select_for_update().get(pk=order.pk)

            # Calculate old delivered loan contribution before any changes.
            old_delivered_value = sum(
                Decimal(str(i.net_delivered)) * i.unit_price
                for i in order_locked.items.all()
            )

            # Update order metadata fields via serializer.
            ser = self.get_serializer(order_locked, data=request.data, partial=partial)
            ser.is_valid(raise_exception=True)
            updated_order = ser.save()

            if items_data is not None:
                existing_ids = set(order_locked.items.values_list("id", flat=True))
                submitted_ids = set()

                for item_row in items_data:
                    item_id = item_row.get("id")
                    if item_id and item_id in existing_ids:
                        # Update existing item.
                        oi = order_locked.items.get(pk=item_id)
                        oi.unit_price = Decimal(str(item_row.get("unit_price", oi.unit_price)))
                        oi.quantity = int(item_row.get("quantity", oi.quantity))
                        oi.save(update_fields=["unit_price", "quantity"])
                        submitted_ids.add(item_id)
                    else:
                        # Create new item.
                        oi = OrderItem.objects.create(
                            order=order_locked,
                            product_id=item_row["product"],
                            unit_price=Decimal(str(item_row["unit_price"])),
                            quantity=int(item_row["quantity"]),
                        )
                        submitted_ids.add(oi.id)

                # Delete items not submitted.
                for old_id in existing_ids - submitted_ids:
                    order_locked.items.filter(pk=old_id).delete()

                # Recalculate delivered value and adjust loan_balance.
                new_delivered_value = sum(
                    Decimal(str(i.net_delivered)) * i.unit_price
                    for i in order_locked.items.all()
                )
                delta = new_delivered_value - old_delivered_value
                if delta != 0:
                    shop = Shop.objects.select_for_update().get(pk=order_locked.shop_id)
                    if order_locked.currency == "UZS":
                        shop.loan_balance_uzs = F("loan_balance_uzs") + delta
                    else:
                        shop.loan_balance_usd = F("loan_balance_usd") + delta
                    shop.save(update_fields=["loan_balance_uzs", "loan_balance_usd"])

            updated_order.refresh_from_db()

        return Response(OrderDetailSerializer(updated_order).data)

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

            items_by_id = {i.id: i for i in order.items.all()}
            balance_delta = Decimal("0")

            for row in ser.validated_data:
                item = items_by_id.get(row["item_id"])
                if not item or item.order_id != order.id:
                    continue
                delivered = min(row["delivered_quantity"], item.quantity)
                returned = min(row.get("returned_quantity", 0), delivered)
                old_net = max(item.delivered_quantity - item.returned_quantity, 0)
                new_net = max(delivered - returned, 0)
                qty_delta = new_net - old_net
                item.delivered_quantity = delivered
                item.returned_quantity = returned
                item.save(update_fields=["delivered_quantity", "returned_quantity"])

                if qty_delta != 0:
                    # Adjust finished-goods stock by the same net-delivery delta.
                    stock, _ = BakeryProductStock.objects.get_or_create(
                        product_id=item.product_id
                    )
                    BakeryProductStock.objects.filter(pk=stock.pk).update(
                        quantity=F("quantity") - qty_delta
                    )
                    # Accumulate shop loan balance delta (what we newly delivered).
                    balance_delta += Decimal(str(qty_delta)) * item.unit_price

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

            # Apply delta to shop loan balance — delta-based so historical data
            # (e.g. V1-migrated orders without corresponding V2 payments) doesn't
            # corrupt the running balance. Payments use the same approach.
            if balance_delta != 0:
                if order.currency == "UZS":
                    shop.loan_balance_uzs = F("loan_balance_uzs") + balance_delta
                else:
                    shop.loan_balance_usd = F("loan_balance_usd") + balance_delta
                shop.save(update_fields=["loan_balance_uzs", "loan_balance_usd"])

        return Response(OrderDetailSerializer(order).data)

    @action(detail=True, methods=["post"])
    def repeat(self, request, pk=None):
        """Feature #3 — clone this order as a new PENDING order for the same shop."""
        source = self.get_object()
        with transaction.atomic():
            new_order = Order.objects.create(
                shop=source.shop,
                order_date=timezone.localdate(),
                delivery_time=None,  # don't copy stale delivery_time
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
