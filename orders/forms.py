from django import forms
from .models import Order, OrderItem
from decimal import Decimal
from dashboard.models import Payment


class ConfirmDeliveryForm(forms.Form):
    """
    Dynamic form for confirming delivery of an order.
    Expects `order` to be passed in __init__.
    """

    def __init__(self, *args, order=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.order = order

        # Fields for each order item delivered qty (no delivery limit)
        for item in order.items.all():
            self.fields[f"delivered_{item.id}"] = forms.IntegerField(
                label=f"{item.product.name} yetkazilgan",
                min_value=0,
                initial=item.delivered_quantity or 0,
                required=True
            )

        # Field for received cash
        self.fields["received_amount"] = forms.DecimalField(
            label="Olingan summa",
            min_value=0,
            max_digits=12,
            decimal_places=2,
            required=True
        )

    def save(self, user):
        """
        Updates delivery, order status, creates Payment, and updates loan balance.
        """
        all_delivered = True
        partial_delivered = False

        # --- update delivered quantities ---
        for item in self.order.items.all():
            delivered_qty = self.cleaned_data[f"delivered_{item.id}"]
            item.delivered_quantity = delivered_qty
            item.save()

            if delivered_qty == 0:
                all_delivered = False
            elif delivered_qty < item.quantity:
                all_delivered = False
                partial_delivered = True

        # --- update order status ---
        if all_delivered:
            self.order.status = "Delivered"
        elif partial_delivered:
            self.order.status = "Partially Delivered"
        else:
            self.order.status = "Pending"
        self.order.save()

        # --- handle received money ---
        received = Decimal(self.cleaned_data["received_amount"])
        if received > 0:
            Payment.objects.create(
                order=self.order,
                shop=self.order.shop,
                amount=received,
                payment_type="collection",
                collected_by=user if user else None,
                notes=f"Olingan summa (Buyurtma #{self.order.id})"
            )

        # --- update shop loan balance ---
        delivered_total = sum(
            Decimal(i.delivered_quantity) * Decimal(i.unit_price)
            for i in self.order.items.all()
        )

        # Remaining debt = delivered - received
        remaining = delivered_total - received
        if remaining < 0:
            remaining = Decimal(0)

        self.order.shop.loan_balance += remaining
        self.order.shop.save()

        return received
