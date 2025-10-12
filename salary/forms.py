from django import forms
from decimal import Decimal
from .models import SalaryPayment

class SalaryPaymentForm(forms.Form):
    amount = forms.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    note = forms.CharField(widget=forms.Textarea(attrs={"rows":2}), required=False)
