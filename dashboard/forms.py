from django import forms
from shops.models import Shop

class LoanRepaymentForm(forms.Form):
    shop = forms.ModelChoiceField(
        queryset=Shop.objects.all(),
        label="Do‘kon",
        widget=forms.Select(attrs={"class": "border rounded px-3 py-2"})
    )
    amount = forms.DecimalField(
        label="Olingan summa (so'm)",
        min_value=0,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "border rounded px-3 py-2"})
    )
