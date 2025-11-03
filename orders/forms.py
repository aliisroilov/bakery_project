# forms.py
from django import forms
from decimal import Decimal
from .models import Order


class ConfirmDeliveryForm(forms.Form):
    def __init__(self, *args, order=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.order = order

        # Create delivered fields for all items
        for item in order.items.all():
            self.fields[f"delivered_{item.id}"] = forms.IntegerField(
                label=f"{item.product.name} yetkazilgan miqdor",
                min_value=0,
                initial=item.delivered_quantity or 0,
                required=True,
            )

        self.fields["received_amount"] = forms.DecimalField(
            label="Olingan summa (so‘m)",
            min_value=0,
            max_digits=12,
            decimal_places=2,
            required=True,
            initial=Decimal("0.00"),
        )

    def save(self):
        """Only update delivered quantities and status."""
        all_delivered = True
        partial_delivered = False

        # Update item quantities
        for item in self.order.items.all():
            delivered_qty = self.cleaned_data[f"delivered_{item.id}"]
            item.delivered_quantity = delivered_qty
            item.save(update_fields=["delivered_quantity"])

            if delivered_qty < item.quantity:
                all_delivered = False
                if delivered_qty > 0:
                    partial_delivered = True

        # Determine status
        if all_delivered:
            self.order.status = "Delivered"
        elif partial_delivered:
            self.order.status = "Partially Delivered"
        else:
            self.order.status = "Pending"

        # Update received amount
        self.order.received_amount = Decimal(self.cleaned_data["received_amount"])
        self.order.save(update_fields=["status", "received_amount"])
        return self.order
